# nl2sql_app

HR-focused NL2SQL service (Flask): RAG over DWH schema, LangChain `LLMChain`, local Qwen via MLflow `pyfunc`, read-only SQL execution.

## Port (canonical)

The process listens on **8060** inside the container (`gunicorn --bind 0.0.0.0:8060`).  
Prometheus scrapes **`nl2sql_app:8060/metrics`**. Ingress maps **`/nl2sql/`** to this upstream (same port).  
Some docs may mention 8000; the stack standard here is **8060**.

## MLflow registry (`NL2SQL_MODEL_URI`)

Default **`NL2SQL_MODEL_URI`** is **`models:/nl2sql_qwen/latest`**. That URI resolves to the **latest registered version** of the model name `nl2sql_qwen`.

Creating only an **empty Registered Model** row in the MLflow UI (no rows under **Versions**) is **not** enough: MLflow returns *RESOURCE_DOES_NOT_EXIST* until **at least one version** is registered (from an experiment run or manual registration).

Options:

1. Register **version 1+** for `nl2sql_qwen` in MLflow (artifact must exist at that version).
2. Set **`NL2SQL_AUTO_LOG_MODEL=true`** so startup logs a `pyfunc` model under **`NL2SQL_MODEL_NAME`** (heavy; requires base model download and resources).

**Registry vs weights in RAM:** the UI and **`POST /query`** only require a **registered model version** (same rules as `models:/...` resolution above). Weights are loaded **lazily on the first inference** (`mlflow.pyfunc.load_model` inside the LLM call). That avoids OOM at process startup and lets **`GET /`** return immediately.

The **first** `/query` may spike RAM while Hugging Face weights load (**torch.float16** and **`low_cpu_mem_usage`** when registering via [`model/qwen_model.py`](model/qwen_model.py)). That dtype applies to **new** `mlflow.pyfunc` runs; **existing** registered versions keep the Python code and weights layout stored in the artifact until you log a new version. If the container OOMs, raise Docker memory limits or **re-register** after changing `QwenModel`.

**MLflow load retries:** the worker attempts **`mlflow.pyfunc.load_model`** up to **3** times with **1s / 2s / 4s** backoff; only the final failure is logged at warning level.

In **`GET /health`**, **`checks.mlflow_model.registry_ok`** matches **`status`** (registered version exists). **`loaded`** is whether **`mlflow.pyfunc`** is already in memory. HTTP **200** when **database** and **RAG index** are OK; **503** only if either fails.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI (chat + D3) |
| POST | `/query` | JSON `{"question":"..."}` → `sql`, `data`, `chart`, `latency_ms` |
| POST | `/debug/rag` | JSON `{"question":"..."}` → JSON array of `{table, score, columns}` per retrieved chunk |
| GET | `/health` | JSON: DB + RAG drive HTTP 200/503. **`checks.mlflow_model`**: **`registry_ok`** / **`status`** = model registered; **`loaded`** = pyfunc in RAM; **`loaded_latency_ms`** |
| GET | `/metrics` | Prometheus text exposition |

## Debug mode

Set **`NL2SQL_DEBUG=true`** (see root `.env.example` and `docker-compose.yml`).  
Then `POST /query` includes a **`debug`** object: `trace_id`, `tables`, `prompt`, `latency`, `rows`, `retry_count`, `sql_before_retry` (set when an execution retry happened), `rag_scores`.

Every request gets a **`trace_id`** (UUID). It appears in structured JSON logs and in **`trace_id`** on error responses (`4xx` from `/query`).

## Metrics (Prometheus)

Label names on counters/histograms: **`status`** (`success` \| `error`), **`stage`** (`generation` \| `validation` \| `execution`) where applicable.

- **`nl2sql_request_count_total`** — completed `/query` outcomes (HTTP-level).
- **`nl2sql_total_latency_seconds`** — wall-clock per request (same semantics as legacy histogram below).
- **`nl2sql_request_latency_seconds`** — kept for compatibility; mirrors total latency observations.
- **`nl2sql_sql_execution_latency_seconds`** — successful `SELECT` execution time only.
- **`nl2sql_sql_*_errors_total`** — validation / generation / execution failures.
- **`nl2sql_rows_returned`** — row count (histogram; bucket `0` included); labeled.
- **`nl2sql_rag_retrieved_tables_count`** — distinct tables returned by RAG per request.
- **`nl2sql_retry_total`** — label **`stage`**: `validation` \| `execution` (validation vs execution retries).
- **`nl2sql_cache_hit_total`** — reserved for future HTTP/SQL caching (no increments yet).

## Logs

JSON to stdout via `observability/json_logging.py`.  
Stage events: `rag_retrieval`, `sql_generation`, `sql_validation`, `sql_execution` (`observability/stage_log.py`).  
Pipeline summary: `event=nl2sql_pipeline` with `trace_id`, `prompt_preview` (500 chars), SQL, validation result, timings, retries.

## Grafana

Dashboard file: `infra/monitoring/grafana/dashboards/nl2sql_dashboard.json` (uid `nl2sql-hr`, folder **DataOps** via provisioning).  
Symlink copy: `infra/grafana/dashboards/nl2sql_dashboard.json`.

Panels include RPS, total latency p95, SQL execution latency p95, error rate, avg rows, validation/generation errors, retry rate, RAG table count.

## Retry behaviour

1. **Validation**: up to 2 attempts; on failure the model receives a correction prompt.  
2. **Execution**: up to 2 attempts only for PostgreSQL errors classified as retryable (syntax / missing relation or column per `nl2sql/db.py`). **Empty result (0 rows) is not an error** and does not trigger retry.
