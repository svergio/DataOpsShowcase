# Quality and monitoring

Operational quality checks and observability are grouped under `monitoring/quality/` so they stay separate from ETL/ELT code paths.

## Quick links

- Runbook: `monitoring/quality/docs/runbook.md`
- dbt DQC selector: `dqc_all_tests` in `dbt/selectors.yml`
- Ingress smoke: `make smoke` (see `scripts/smoke_ingress.sh`)
- Full P0 checks: `make p0-verify`

## Contracts

- **Ingress (canonical):** `/`, `/dbt-web/`, `/dbt-api/v1/*` (rewritten to backend `/api/`), `/airflow/`, `/mlflow/`, `/grafana/`.
- **`meta.pipeline_runs`:** `status` values `running`, `success`, `failed`; `finished_at` set when a run completes (see `services/common/run_metadata.py`).
- **Grafana:** Prometheus panels use metrics pushed to Pushgateway (`dag_*`, `dataops_dbt_*`, `task_duration_seconds_*`). SQL panels use `meta.v_pipeline_runs_recent` and `meta.v_dq_recent` via datasource **PostgreSQL DWH** (`uid: PGDWH`).

## Debugging flow

1. Confirm URLs: `make smoke`.
2. Confirm dbt: `dbt source freshness` and `dbt test --selector dqc_all_tests`; inspect `dwh_dq` for stored failures.
3. Confirm lineage in `meta.*` views; open **Meta telemetry (Postgres)** in Grafana.
