from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass

import mlflow
from flask import Flask, Response, jsonify, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from model.qwen_model import QwenModel
from nl2sql.chain import NL2SQLService
from nl2sql.db import DBClient
from observability import json_logging
from observability import metrics as prom
from rag.embeddings import LocalEmbeddings
from rag.schema_loader import SchemaLoader
from rag.schema_utils import columns_from_doc, parse_table_name
from rag.vectorstore import SchemaVectorStore

json_logging.setup_json_logging(
    level=getattr(logging, os.environ.get("NL2SQL_LOG_LEVEL", "INFO").upper(), logging.INFO),
)
logger = logging.getLogger(__name__)

PUBLIC_MODEL_UNAVAILABLE_MSG = (
    "MLflow model is not available. Register at least one model version, "
    "or set NL2SQL_AUTO_LOG_MODEL=true. Details are logged server-side."
)


def _error_stage(exc: BaseException) -> str:
    text = str(exc).lower()
    if "sql_execution" in text or "undefined" in text or "syntax error" in text:
        return "execution"
    if "validation" in text:
        return "validation"
    return "generation"


def _record_request_http(*, ok: bool, elapsed_s: float, stage: str) -> None:
    status = "success" if ok else "error"
    prom.REQUEST_COUNT.labels(status, stage).inc()
    prom.TOTAL_LATENCY_SECONDS.labels(status, stage).observe(elapsed_s)
    prom.REQUEST_LATENCY_SECONDS.labels(status, stage).observe(elapsed_s)


def _log_mlflow_load_error_if_any(svc: NL2SQLService) -> None:
    raw = getattr(svc.llm, "load_error", None)
    if raw:
        logger.warning("nl2sql_mlflow_load_error: %s", raw)


def _metrics_exposed() -> bool:
    return os.environ.get("NL2SQL_EXPOSE_METRICS", "true").lower() == "true"


@dataclass(frozen=True)
class AppConfig:
    db_url: str
    mlflow_tracking_uri: str
    mlflow_model_uri: str
    embedding_model_name: str
    rag_top_k: int
    auto_log_model: bool
    model_name: str
    nl2sql_debug: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        db_url = os.environ.get(
            "DB_URL",
            "postgresql+psycopg2://olap_user:olap_pass@postgres_olap:5432/techmart_dwh",
        )
        mlflow_tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow_model_uri = os.environ.get("NL2SQL_MODEL_URI", "models:/nl2sql_qwen/latest")
        embedding_model_name = os.environ.get(
            "NL2SQL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        rag_top_k = int(os.environ.get("NL2SQL_RAG_TOP_K", "3"))
        auto_log_model = os.environ.get("NL2SQL_AUTO_LOG_MODEL", "false").lower() == "true"
        model_name = os.environ.get("NL2SQL_MODEL_NAME", "nl2sql_qwen")
        nl2sql_debug = os.environ.get("NL2SQL_DEBUG", "false").lower() == "true"
        return cls(
            db_url=db_url,
            mlflow_tracking_uri=mlflow_tracking_uri,
            mlflow_model_uri=mlflow_model_uri,
            embedding_model_name=embedding_model_name,
            rag_top_k=rag_top_k,
            auto_log_model=auto_log_model,
            model_name=model_name,
            nl2sql_debug=nl2sql_debug,
        )


def _ensure_model_logged(cfg: AppConfig) -> None:
    if not cfg.auto_log_model:
        return
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    client = mlflow.tracking.MlflowClient()
    try:
        existing = client.search_model_versions(
            filter_string=f"name='{cfg.model_name}'",
            max_results=1,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "nl2sql_autolog_precheck_unavailable (MLflow unreachable); skip bootstrap log: %s",
            exc,
        )
        return
    if existing:
        logger.info(
            "nl2sql_skip_autolog model=%s already has registered version(s)",
            cfg.model_name,
        )
        return
    with mlflow.start_run(run_name="nl2sql_model_bootstrap"):
        mlflow.pyfunc.log_model(
            artifact_path="nl2sql_qwen",
            python_model=QwenModel(),
            registered_model_name=cfg.model_name,
            model_config={
                "model_id": os.environ.get("NL2SQL_BASE_MODEL_ID", "Qwen/Qwen2.5-3B-Instruct"),
                "max_new_tokens": int(os.environ.get("NL2SQL_MAX_NEW_TOKENS", "256")),
                "temperature": float(os.environ.get("NL2SQL_TEMPERATURE", "0.0")),
            },
            pip_requirements=[
                "mlflow==2.15.1",
                "transformers==4.44.2",
                "torch==2.3.1",
                "pandas==2.2.2",
            ],
        )


def _build_service(cfg: AppConfig) -> NL2SQLService:
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    _ensure_model_logged(cfg)
    db = DBClient(cfg.db_url)
    loader = SchemaLoader(db.engine)
    schema_rows = loader.load_schema_documents()
    embeddings = LocalEmbeddings(cfg.embedding_model_name)
    vectorstore = SchemaVectorStore.from_documents(schema_rows, embeddings)
    return NL2SQLService(
        db_client=db,
        vectorstore=vectorstore,
        model_uri=cfg.mlflow_model_uri,
        tracking_uri=cfg.mlflow_tracking_uri,
        model_name=cfg.model_name,
        top_k=cfg.rag_top_k,
    )


def create_app() -> Flask:
    cfg = AppConfig.from_env()
    service = _build_service(cfg)
    root = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
        static_url_path="/static",
    )
    app.config["NL2SQL_SERVICE"] = service
    app.config["NL2SQL_DEBUG"] = cfg.nl2sql_debug
    app.config["ASSET_VERSION"] = os.environ.get("NL2SQL_ASSET_VERSION", "3")
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = int(
        os.environ.get("NL2SQL_STATIC_MAX_AGE", "120"),
    )

    @app.get("/health")
    def health() -> tuple[Response, int]:
        svc: NL2SQLService = app.config["NL2SQL_SERVICE"]

        t0 = time.perf_counter()
        db_ok = svc.db_client.ping()
        db_ms = int((time.perf_counter() - t0) * 1000)

        t1 = time.perf_counter()
        registry_ok = svc.model_registered()
        registry_ms = int((time.perf_counter() - t1) * 1000)

        t_reg = time.perf_counter()
        loaded_ok = svc.model_ready()
        loaded_ms = int((time.perf_counter() - t_reg) * 1000)

        t2 = time.perf_counter()
        rag_ok = svc.rag_index_ready()
        rag_ms = int((time.perf_counter() - t2) * 1000)

        core_ok = db_ok and rag_ok
        mlflow_track_ok = registry_ok
        full_ok = core_ok and mlflow_track_ok and loaded_ok
        payload = {
            "status": (
                "ok"
                if full_ok
                else ("degraded" if core_ok else "unavailable")
            ),
            "checks": {
                "database": {"status": "ok" if db_ok else "fail", "latency_ms": db_ms},
                "mlflow_model": {
                    "registry_ok": mlflow_track_ok,
                    "status": "ok" if mlflow_track_ok else "fail",
                    "latency_ms": registry_ms,
                    "loaded": loaded_ok,
                    "loaded_latency_ms": loaded_ms,
                },
                "rag_index": {"status": "ok" if rag_ok else "fail", "latency_ms": rag_ms},
            },
        }
        return jsonify(payload), 200 if core_ok else 503

    @app.get("/metrics")
    def metrics() -> Response:
        if not _metrics_exposed():
            return Response("Not Found\n", status=404, mimetype="text/plain")
        data = generate_latest()
        return Response(data, mimetype=CONTENT_TYPE_LATEST)

    @app.get("/")
    def index() -> str:
        svc: NL2SQLService = app.config["NL2SQL_SERVICE"]
        registry_ok = svc.model_registered()
        loaded_ok = svc.model_ready()
        load_err = getattr(svc.llm, "load_error", None)
        if load_err:
            _log_mlflow_load_error_if_any(svc)
        return render_template(
            "index.html",
            show_registry_warning=not registry_ok,
            show_load_error=bool(load_err),
            registry_ok=registry_ok,
            model_loaded=loaded_ok,
            asset_version=app.config["ASSET_VERSION"],
        )

    @app.post("/debug/rag")
    def debug_rag() -> Response:
        if not app.config.get("NL2SQL_DEBUG"):
            return jsonify({"error": "debug endpoints disabled"}), 404
        svc: NL2SQLService = app.config["NL2SQL_SERVICE"]
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        if not question:
            return jsonify({"error": "question is required"}), 400
        docs, scores, _ = svc.rag_search(question)
        chunks: list[dict[str, object]] = []
        for doc, score in zip(docs, scores, strict=True):
            chunks.append(
                {
                    "table": parse_table_name(doc) or "",
                    "score": float(score),
                    "columns": columns_from_doc(doc),
                },
            )
        return jsonify(chunks)

    @app.post("/query")
    def query() -> Response:
        svc: NL2SQLService = app.config["NL2SQL_SERVICE"]
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        trace_id = str(uuid.uuid4())
        started = time.perf_counter()
        if not question:
            elapsed = time.perf_counter() - started
            _record_request_http(ok=False, elapsed_s=elapsed, stage="validation")
            return jsonify({"error": "question is required", "trace_id": trace_id}), 400
        if not svc.model_registered():
            _log_mlflow_load_error_if_any(svc)
            return jsonify({"error": PUBLIC_MODEL_UNAVAILABLE_MSG, "trace_id": trace_id}), 503
        debug_flag = bool(app.config.get("NL2SQL_DEBUG"))
        try:
            result = svc.answer_question(question, debug=debug_flag, trace_id=trace_id)
        except RuntimeError as exc:
            elapsed = time.perf_counter() - started
            _record_request_http(ok=False, elapsed_s=elapsed, stage="generation")
            _log_mlflow_load_error_if_any(svc)
            logger.error(
                "nl2sql_mlflow_runtime_failed",
                exc_info=True,
                extra={
                    "nl2sql": {
                        "event": "nl2sql_mlflow_runtime_failed",
                        "trace_id": trace_id,
                        "question": question,
                        "error": str(exc),
                    },
                },
            )
            return jsonify(
                {
                    "error": str(exc) or PUBLIC_MODEL_UNAVAILABLE_MSG,
                    "trace_id": trace_id,
                },
                502,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - started
            stage = _error_stage(exc)
            _record_request_http(ok=False, elapsed_s=elapsed, stage=stage)
            logger.error(
                "nl2sql_query_failed",
                exc_info=True,
                extra={
                    "nl2sql": {
                        "event": "nl2sql_query_failed",
                        "trace_id": trace_id,
                        "question": question,
                        "error": str(exc),
                    },
                },
            )
            return jsonify({"error": str(exc), "trace_id": trace_id}), 400
        elapsed = time.perf_counter() - started
        _record_request_http(ok=True, elapsed_s=elapsed, stage="execution")
        latency_ms = int(elapsed * 1000)
        result["latency_ms"] = latency_ms
        return jsonify(result)

    return app


app = create_app()
