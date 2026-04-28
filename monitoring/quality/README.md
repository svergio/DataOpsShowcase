# Quality and monitoring (DQC)

This zone groups data-quality operations and assets that are intentionally separate from ETL/ELT application code.

## Layout

- `dbt/selectors.yml` in the dbt project defines `dqc_all_tests` (all generic tests; failures land in `dwh_dq` per `dbt/dbt_project.yml`).
- `monitoring/quality/sql/` reserved for non-dbt SQL checks.
- `monitoring/quality/docs/runbook.md` runbook and SLA notes.
- `monitoring/quality/grafana/meta-telemetry-postgres.json` copy of the Grafana dashboard backed by `meta.*` views (source of truth lives under `infra/monitoring/grafana/dashboards/`).

## Run DQC (dbt)

From the repository root, with PostgreSQL (OLAP) reachable and dbt installed:

```bash
cd dbt
dbt source freshness --profiles-dir . --project-dir .
dbt test --selector dqc_all_tests --profiles-dir . --project-dir .
```

Or use `./monitoring/quality/scripts/run_dqc.sh`.

## Orchestration split (target)

- ETL/ELT DAGs publish datasets and update watermarks.
- A separate quality stage (dbt tests, `meta.dq_results`, dashboards) validates published layers without owning transformation logic.

## URLs and smoke

Canonical ingress paths are documented in `scripts/smoke_ingress.sh`. Run `make smoke` from the showcase root.
