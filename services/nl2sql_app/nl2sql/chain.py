from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import mlflow
import pandas as pd
from langchain.chains import LLMChain
from pydantic.v1 import PrivateAttr
from langchain.prompts import PromptTemplate
from langchain_core.language_models.llms import LLM

from nl2sql.db import DBClient, is_retryable_execution_error
from nl2sql.prompts import (
    build_correction_prompt,
    build_execution_correction_prompt,
    build_prompt,
)
from nl2sql.validator import validate_sql
from mlflow_registry import is_model_registered
from observability import metrics as prom
from observability.stage_log import log_nl2sql_stage
from rag.schema_utils import tables_from_docs
from rag.vectorstore import SchemaVectorStore

logger = logging.getLogger("nl2sql.pipeline")

PROMPT_LOG_MAX = 500
PROMPT_DEBUG_MAX = 4000
MAX_VALIDATION_ATTEMPTS = 2
MAX_EXECUTION_ATTEMPTS = 2

_MLFLOW_PYFUNC_LOAD_ATTEMPTS = 3
_MLFLOW_PYFUNC_BACKOFF_SEC = (1.0, 2.0, 4.0)


class MLflowPyfuncLLM(LLM):
    model_uri: str
    tracking_uri: str
    _pyfunc_model: Any = PrivateAttr(default=None)
    _load_error_msg: str | None = PrivateAttr(default=None)
    _load_lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def __init__(self, model_uri: str, tracking_uri: str) -> None:
        super().__init__(model_uri=model_uri, tracking_uri=tracking_uri)
        mlflow.set_tracking_uri(tracking_uri)

    def _ensure_pyfunc_loaded(self) -> None:
        if self._pyfunc_model is not None:
            return
        if self._load_error_msg is not None:
            return
        with self._load_lock:
            if self._pyfunc_model is not None:
                return
            if self._load_error_msg is not None:
                return
            last_exc: BaseException | None = None
            for attempt in range(_MLFLOW_PYFUNC_LOAD_ATTEMPTS):
                try:
                    self._pyfunc_model = mlflow.pyfunc.load_model(self.model_uri)
                    return
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt < _MLFLOW_PYFUNC_LOAD_ATTEMPTS - 1:
                        time.sleep(_MLFLOW_PYFUNC_BACKOFF_SEC[attempt])
            self._load_error_msg = str(last_exc) if last_exc else "MLflow pyfunc load failed"
            logger.warning(
                "mlflow_pyfunc_load_failed uri=%s attempts=%s error=%s",
                self.model_uri,
                _MLFLOW_PYFUNC_LOAD_ATTEMPTS,
                last_exc,
                exc_info=last_exc,
            )

    @property
    def _llm_type(self) -> str:
        return "mlflow_pyfunc_qwen"

    def is_loaded(self) -> bool:
        return self._pyfunc_model is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error_msg if not self.is_loaded() else None

    def _call(self, prompt: str, stop: list[str] | None = None, **kwargs: object) -> str:
        self._ensure_pyfunc_loaded()
        if self._pyfunc_model is None:
            raise RuntimeError(self._load_error_msg or "MLflow pyfunc model is not loaded")
        frame = pd.DataFrame([{"prompt": prompt}])
        result = self._pyfunc_model.predict(frame)
        text = result[0] if isinstance(result, (list, tuple)) else str(result)
        if stop:
            for token in stop:
                text = text.split(token)[0]
        return text.strip()


class NL2SQLService:
    def __init__(
        self,
        db_client: DBClient,
        vectorstore: SchemaVectorStore,
        model_uri: str,
        tracking_uri: str,
        model_name: str,
        top_k: int,
    ) -> None:
        self.db_client = db_client
        self.vectorstore = vectorstore
        self.top_k = top_k
        self._model_uri = model_uri
        self._tracking_uri = tracking_uri
        self._model_name = model_name
        self.llm = MLflowPyfuncLLM(model_uri=model_uri, tracking_uri=tracking_uri)
        self.chain = LLMChain(
            llm=self.llm,
            prompt=PromptTemplate(
                input_variables=["final_prompt"],
                template="{final_prompt}",
            ),
        )

    def rag_index_ready(self) -> bool:
        return self.vectorstore.document_count > 0 and self.vectorstore.index.ntotal > 0

    def model_ready(self) -> bool:
        return self.llm.is_loaded()

    def model_registered(self) -> bool:
        return is_model_registered(
            tracking_uri=self._tracking_uri,
            model_uri=self._model_uri,
            model_name=self._model_name,
        )

    def _choose_chart(self, rows: list[dict[str, object]]) -> str:
        if not rows:
            return "none"
        col_count = len(rows[0])
        if col_count == 1:
            return "none"
        if col_count == 2:
            return "bar"
        return "table"

    def rag_search(self, question: str) -> tuple[list[str], list[float], list[str]]:
        docs, scores = self.vectorstore.search_with_scores(question, self.top_k)
        tables = tables_from_docs(docs)
        return docs, scores, tables

    def answer_question(
        self,
        question: str,
        *,
        debug: bool = False,
        trace_id: str = "",
        stage_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        if stage_callback is not None:
            stage_callback("model_load")
        self.llm._ensure_pyfunc_loaded()
        if not self.model_ready():
            err = getattr(self.llm, "load_error", None)
            raise RuntimeError(
                err
                or "NL2SQL LLM is not available. Register the model in MLflow (see NL2SQL_MODEL_URI) "
                "or set NL2SQL_AUTO_LOG_MODEL=true for bootstrap.",
            )
        total_started = time.perf_counter()
        rag_started = time.perf_counter()
        if stage_callback is not None:
            stage_callback("rag_retrieval")
        context_docs, rag_scores, retrieved_tables = self.rag_search(question)
        context_text = "\n".join(context_docs)
        rag_latency_ms = int((time.perf_counter() - rag_started) * 1000)
        prom.RAG_RETRIEVED_TABLES_COUNT.labels("success", "generation").observe(len(retrieved_tables))

        log_nl2sql_stage(
            trace_id,
            "rag_retrieval",
            question=question,
            retrieved_tables=retrieved_tables,
            latency_ms=rag_latency_ms,
            rag_scores=rag_scores,
        )

        validation_retry_count = 0
        execution_retry_count = 0
        sql_before_retry: str | None = None
        prompt = build_prompt(question, context_text)
        prompt_preview = prompt[:PROMPT_LOG_MAX]

        sql: str | None = None
        raw_sql_last = ""
        validation_result = "pending"
        sql_gen_latency_ms = 0
        query_latency_ms = 0
        rows: list[dict[str, object]] = []
        chart = "none"

        for exec_attempt in range(MAX_EXECUTION_ATTEMPTS):
            sql = None
            for val_attempt in range(1, MAX_VALIDATION_ATTEMPTS + 1):
                gen_started = time.perf_counter()
                if stage_callback is not None:
                    stage_callback("sql_generation")
                log_nl2sql_stage(
                    trace_id,
                    "sql_generation",
                    question=question,
                    validation_attempt=val_attempt,
                    execution_attempt=exec_attempt + 1,
                )
                raw_sql = self.chain.run({"final_prompt": prompt})
                raw_sql_last = raw_sql
                sql_gen_latency_ms += int((time.perf_counter() - gen_started) * 1000)

                log_nl2sql_stage(
                    trace_id,
                    "sql_validation",
                    raw_sql_preview=raw_sql.strip()[:200],
                )
                if stage_callback is not None:
                    stage_callback("sql_validation")
                try:
                    sql = validate_sql(raw_sql)
                    validation_result = "ok"
                    break
                except ValueError as exc:
                    validation_result = f"error: {exc}"
                    prom.SQL_VALIDATION_ERRORS.labels("error", "validation").inc()
                    if val_attempt >= MAX_VALIDATION_ATTEMPTS:
                        prom.SQL_GENERATION_ERRORS.labels("error", "generation").inc()
                        total_ms = int((time.perf_counter() - total_started) * 1000)
                        self._log_pipeline(
                            trace_id=trace_id,
                            question=question,
                            retrieved_tables=retrieved_tables,
                            prompt_preview=prompt_preview,
                            generated_sql=raw_sql_last.strip(),
                            validation_result=validation_result,
                            execution_time_ms=None,
                            total_time_ms=total_ms,
                            row_count=None,
                            validation_retries=validation_retry_count,
                            execution_retries=execution_retry_count,
                            error="sql_validation_failed",
                        )
                        raise ValueError(
                            f"SQL validation failed after {MAX_VALIDATION_ATTEMPTS} attempts: {exc}",
                        ) from exc
                    validation_retry_count += 1
                    prom.RETRY_TOTAL.labels("validation").inc()
                    prompt = build_correction_prompt(
                        question,
                        context_text,
                        invalid_sql=raw_sql.strip(),
                        error=str(exc),
                    )
                    prompt_preview = prompt[:PROMPT_LOG_MAX]

            assert sql is not None

            exec_started = time.perf_counter()
            if stage_callback is not None:
                stage_callback("sql_execution")
            log_nl2sql_stage(trace_id, "sql_execution", sql_preview=sql[:500])
            try:
                rows = self.db_client.run_select(sql)
            except Exception as exc:  # noqa: BLE001
                query_latency_ms = int((time.perf_counter() - exec_started) * 1000)
                prom.SQL_EXECUTION_ERRORS.labels("error", "execution").inc()
                if (
                    is_retryable_execution_error(exc)
                    and exec_attempt < MAX_EXECUTION_ATTEMPTS - 1
                ):
                    execution_retry_count += 1
                    prom.RETRY_TOTAL.labels("execution").inc()
                    if sql_before_retry is None:
                        sql_before_retry = sql
                    prompt = build_execution_correction_prompt(
                        question,
                        context_text,
                        failed_sql=sql,
                        error=str(exc),
                    )
                    prompt_preview = prompt[:PROMPT_LOG_MAX]
                    continue

                total_ms = int((time.perf_counter() - total_started) * 1000)
                self._log_pipeline(
                    trace_id=trace_id,
                    question=question,
                    retrieved_tables=retrieved_tables,
                    prompt_preview=prompt_preview,
                    generated_sql=sql,
                    validation_result=validation_result,
                    execution_time_ms=query_latency_ms,
                    total_time_ms=total_ms,
                    row_count=0,
                    validation_retries=validation_retry_count,
                    execution_retries=execution_retry_count,
                    error=f"sql_execution: {exc}",
                )
                raise

            query_latency_ms = int((time.perf_counter() - exec_started) * 1000)
            prom.SQL_EXECUTION_LATENCY_SECONDS.labels("success", "execution").observe(
                query_latency_ms / 1000.0,
            )
            break

        chart = self._choose_chart(rows)
        total_ms = int((time.perf_counter() - total_started) * 1000)

        prom.ROWS_RETURNED.labels("success", "execution").observe(len(rows))

        self._log_pipeline(
            trace_id=trace_id,
            question=question,
            retrieved_tables=retrieved_tables,
            prompt_preview=prompt_preview,
            generated_sql=sql,
            validation_result=validation_result,
            execution_time_ms=query_latency_ms,
            total_time_ms=total_ms,
            row_count=len(rows),
            validation_retries=validation_retry_count,
            execution_retries=execution_retry_count,
            error=None,
        )

        with mlflow.start_run(run_name="nl2sql_query", nested=True):
            mlflow.log_param("question", question)
            mlflow.log_param("chart", chart)
            mlflow.log_param("rag_top_k", self.top_k)
            mlflow.log_param("trace_id", trace_id)
            mlflow.log_text(prompt, "prompt.txt")
            mlflow.log_text(sql, "generated.sql")
            mlflow.log_metric("rows", len(rows))
            mlflow.log_metric("rag_latency_ms", rag_latency_ms)
            mlflow.log_metric("sql_gen_latency_ms", sql_gen_latency_ms)
            mlflow.log_metric("query_latency_ms", query_latency_ms)

        result: dict[str, Any] = {
            "sql": sql,
            "data": rows,
            "chart": chart,
        }
        if debug:
            result["debug"] = {
                "trace_id": trace_id,
                "tables": retrieved_tables,
                "prompt": prompt[:PROMPT_DEBUG_MAX],
                "latency": total_ms,
                "rows": len(rows),
                "retry_count": validation_retry_count + execution_retry_count,
                "sql_before_retry": sql_before_retry,
                "rag_scores": rag_scores,
            }
        return result

    def _log_pipeline(
        self,
        *,
        trace_id: str,
        question: str,
        retrieved_tables: list[str],
        prompt_preview: str,
        generated_sql: str,
        validation_result: str,
        execution_time_ms: int | None,
        total_time_ms: int | None,
        row_count: int | None,
        validation_retries: int,
        execution_retries: int,
        error: str | None,
    ) -> None:
        preview = (prompt_preview or "")[:PROMPT_LOG_MAX]
        payload = {
            "event": "nl2sql_pipeline",
            "trace_id": trace_id,
            "question": question,
            "retrieved_tables": retrieved_tables,
            "prompt_preview": preview,
            "generated_sql": generated_sql,
            "validation_result": validation_result,
            "execution_time_ms": execution_time_ms,
            "total_time_ms": total_time_ms,
            "row_count": row_count,
            "validation_retries": validation_retries,
            "execution_retries": execution_retries,
            "retry_count": validation_retries + execution_retries,
            "error": error,
        }
        logger.info("nl2sql_pipeline", extra={"nl2sql": payload})
