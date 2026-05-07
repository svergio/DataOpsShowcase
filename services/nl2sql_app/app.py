from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass

import mlflow
import redis
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


def _classify_error(error_text: str) -> str:
    lowered = error_text.lower()
    if "forbidden sql statement" in lowered:
        return "forbidden_keyword"
    if "table is not whitelisted" in lowered:
        return "unknown_table"
    if "empty sql generated" in lowered:
        return "empty_sql"
    if "invalid expression" in lowered or "unexpected token" in lowered:
        return "parse_error"
    if "syntax error" in lowered:
        return "sql_syntax_error"
    if "timeout" in lowered:
        return "timeout"
    return "runtime_error"


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
    redis_url: str
    redis_queue_key: str
    redis_job_ttl_sec: int
    profile: str
    base_model_id: str
    max_new_tokens: int
    temperature: float

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
        redis_url = os.environ.get("NL2SQL_REDIS_URL", "redis://redis:6379/5")
        redis_queue_key = os.environ.get("NL2SQL_QUEUE_KEY", "nl2sql:queue")
        redis_job_ttl_sec = int(os.environ.get("NL2SQL_JOB_TTL_SEC", "3600"))
        profile = os.environ.get("NL2SQL_PROFILE", "stable").lower()
        if profile == "fast":
            base_model_id = os.environ.get("NL2SQL_FAST_MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct")
            max_new_tokens = int(os.environ.get("NL2SQL_FAST_MAX_NEW_TOKENS", "96"))
            temperature = float(os.environ.get("NL2SQL_FAST_TEMPERATURE", "0.0"))
        else:
            base_model_id = os.environ.get("NL2SQL_STABLE_MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct")
            max_new_tokens = int(os.environ.get("NL2SQL_STABLE_MAX_NEW_TOKENS", "128"))
            temperature = float(os.environ.get("NL2SQL_STABLE_TEMPERATURE", "0.0"))
        return cls(
            db_url=db_url,
            mlflow_tracking_uri=mlflow_tracking_uri,
            mlflow_model_uri=mlflow_model_uri,
            embedding_model_name=embedding_model_name,
            rag_top_k=rag_top_k,
            auto_log_model=auto_log_model,
            model_name=model_name,
            nl2sql_debug=nl2sql_debug,
            redis_url=redis_url,
            redis_queue_key=redis_queue_key,
            redis_job_ttl_sec=redis_job_ttl_sec,
            profile=profile,
            base_model_id=base_model_id,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
        )


class RedisQueryQueue:
    def __init__(
        self,
        *,
        redis_url: str,
        queue_key: str,
        job_ttl_sec: int,
        service: NL2SQLService,
        debug_enabled: bool,
    ) -> None:
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.queue_key = queue_key
        self.job_ttl_sec = job_ttl_sec
        self.service = service
        self.debug_enabled = debug_enabled
        self._thread: threading.Thread | None = None

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"nl2sql:job:{job_id}"

    def enqueue(self, question: str) -> str:
        job_id = str(uuid.uuid4())
        job_key = self._job_key(job_id)
        now_ms = int(time.time() * 1000)
        queue_position = self.redis.llen(self.queue_key) + 1
        self.redis.hset(
            job_key,
            mapping={
                "status": "queued",
                "stage": "queued",
                "question": question,
                "queue_position": queue_position,
                "created_at_ms": now_ms,
                "updated_at_ms": now_ms,
            },
        )
        self.redis.expire(job_key, self.job_ttl_sec)
        self.redis.rpush(self.queue_key, job_id)
        return job_id

    def get_status(self, job_id: str) -> dict[str, object] | None:
        job_key = self._job_key(job_id)
        data = self.redis.hgetall(job_key)
        if not data:
            return None
        status = data.get("status", "queued")
        payload: dict[str, object] = {
            "job_id": job_id,
            "status": status,
            "stage": data.get("stage", "queued"),
            "created_at_ms": int(data.get("created_at_ms", "0") or 0),
            "updated_at_ms": int(data.get("updated_at_ms", "0") or 0),
            "elapsed_ms": max(
                0,
                int(data.get("updated_at_ms", "0") or 0) - int(data.get("created_at_ms", "0") or 0),
            ),
        }
        if status == "queued":
            current_pos = self.redis.lpos(self.queue_key, job_id)
            if current_pos is not None:
                payload["queue_position"] = int(current_pos) + 1
            elif data.get("queue_position"):
                payload["queue_position"] = int(data["queue_position"])
        if status == "done" and data.get("result"):
            payload["result"] = json.loads(data["result"])
        if status == "error":
            payload["error"] = data.get("error_message", data.get("error", "unknown error"))
            payload["error_message"] = data.get("error_message", data.get("error", "unknown error"))
            payload["error_code"] = data.get("error_code", "runtime_error")
            if data.get("trace_id"):
                payload["trace_id"] = data["trace_id"]
        return payload

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="nl2sql-redis-worker")
        self._thread.start()

    def _set_job_state(self, job_id: str, mapping: dict[str, object]) -> None:
        job_key = self._job_key(job_id)
        to_write = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in mapping.items()}
        to_write["updated_at_ms"] = str(int(time.time() * 1000))
        self.redis.hset(job_key, mapping=to_write)
        self.redis.expire(job_key, self.job_ttl_sec)

    def _worker_loop(self) -> None:
        logger.info("nl2sql_queue_worker_started queue_key=%s", self.queue_key)
        while True:
            try:
                item = self.redis.blpop(self.queue_key, timeout=5)
                if not item:
                    continue
                _, job_id = item
                job_key = self._job_key(job_id)
                question = self.redis.hget(job_key, "question")
                if not question:
                    self._set_job_state(
                        job_id,
                        {
                            "status": "error",
                            "stage": "error",
                            "error_code": "validation_error",
                            "error_message": "missing question",
                        },
                    )
                    continue
                self._set_job_state(job_id, {"status": "processing", "stage": "processing"})
                trace_id = str(uuid.uuid4())
                started = time.perf_counter()

                def _on_stage(stage_name: str) -> None:
                    self._set_job_state(job_id, {"status": "processing", "stage": stage_name})

                result = self.service.answer_question(
                    question,
                    debug=self.debug_enabled,
                    trace_id=trace_id,
                    stage_callback=_on_stage,
                )
                if "latency_ms" not in result:
                    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
                self._set_job_state(job_id, {"status": "done", "stage": "done", "result": result})
            except Exception as exc:  # noqa: BLE001
                if "job_id" in locals():
                    err = str(exc) or "nl2sql queue worker failed"
                    self._set_job_state(
                        job_id,
                        {
                            "status": "error",
                            "stage": "error",
                            "error_code": _classify_error(err),
                            "error_message": err,
                            "trace_id": locals().get("trace_id", ""),
                        },
                    )
                logger.exception("nl2sql_queue_worker_unhandled_error: %s", exc)
                time.sleep(1)


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
                "model_id": cfg.base_model_id,
                "max_new_tokens": cfg.max_new_tokens,
                "temperature": cfg.temperature,
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
    query_queue = RedisQueryQueue(
        redis_url=cfg.redis_url,
        queue_key=cfg.redis_queue_key,
        job_ttl_sec=cfg.redis_job_ttl_sec,
        service=service,
        debug_enabled=cfg.nl2sql_debug,
    )
    query_queue.start()
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
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        if not question:
            return jsonify({"error": "question is required"}), 400
        job_id = query_queue.enqueue(question)
        return jsonify({"job_id": job_id, "status": "queued"}), 202

    @app.get("/query/<job_id>")
    def query_status(job_id: str) -> Response:
        status = query_queue.get_status(job_id)
        if status is None:
            return jsonify({"error": "job not found", "job_id": job_id}), 404
        return jsonify(status), 200

    return app


app = create_app()
