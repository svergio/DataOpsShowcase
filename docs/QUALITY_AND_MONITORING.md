# Quality and monitoring (index)

Operational checks split by concern so paths match how tools run:

- **Automated tests and dbt Data Quality**: [TESTING_AND_DATA_QUALITY.md](TESTING_AND_DATA_QUALITY.md) — pytest layouts, `dbt/tests`, selector `dqc_all_tests`, `dwh_dq`, [`scripts/run_dqc.sh`](../scripts/run_dqc.sh).
- **Grafana/Prometheus/meta/logging**: [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md) — canonical dashboards under [`infra/monitoring/grafana/`](../infra/monitoring/grafana/), `meta.*` views, metrics.

Quick commands: `make smoke`, `make p0-verify`, `make dqc-help`.

## Contracts (compact)

- **Ingress:** `/`, `/dbt/`, `/dbt-api/v1/*` (backend `/api/` behind ingress), `/airflow/`, `/mlflow/`, `/grafana/`.
- **`meta.pipeline_runs`:** `status` values `running`, `success`, `failed`; `finished_at` when a run completes (see [`services/common/run_metadata.py`](../services/common/run_metadata.py)).
- **Grafana:** Prometheus panels from Pushgateway (`dag_*`, `dataops_dbt_*`, `task_duration_seconds_*`); SQL panels from `meta.v_pipeline_runs_recent` and `meta.v_dq_recent` via datasource **PostgreSQL DWH** (`uid: PGDWH`).

## Debugging flow

1. URLs: `make smoke`.
2. dbt / DQ failures: `./scripts/run_dqc.sh` or manual `dbt test --selector dqc_all_tests`; inspect `dwh_dq` for stored failures.
3. `meta.*` views and **Meta telemetry (Postgres)** dashboard in Grafana (see OBSERVABILITY doc).
