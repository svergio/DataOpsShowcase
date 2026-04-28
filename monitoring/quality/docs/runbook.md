# Quality & monitoring runbook

## `meta.pipeline_runs`

- Rows are created via `services.common.run_metadata.start_run` (`status='running'`) and closed via `finish_run` with `finished_at`, `status` in `running` | `success` | `failed`, and optional `rows_in`, `rows_out`, `payload`.
- Debugging: query `meta.v_pipeline_runs_recent` or use Grafana dashboard **Meta telemetry (Postgres)**.

## `meta.pipeline_watermarks`

- Read/write through `services.common.watermarks` (table default `meta.pipeline_watermarks`, connection from `configs/pipeline/watermarks.yaml`).
- Debugging: inspect `pipeline_name`, `watermark_value`, `last_run_at` in Postgres (OLAP).

## dbt failures

- Generic tests persist to `dwh_dq.*` when `store_failures: true` (see `dbt/dbt_project.yml`).
- Run `dbt test --selector dqc_all_tests`; inspect relations in schema `dwh_dq`.

## Grafana

- Prometheus: Airflow emits `dag_success_total` / `dag_failure_total` / `task_duration_seconds_*` via Pushgateway listener; dbt emits `dataops_dbt_*` from DAG helpers.
- PostgreSQL datasource **PostgreSQL DWH** (`uid: PGDWH`) serves `meta.v_*` panels on **Meta telemetry (Postgres)**.

## Smoke checklist

See `Makefile` targets `make smoke` and `make p0-verify`.
