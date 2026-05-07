# AGENT CONTEXT (DataOpsShowcase)

This file is optimized for Cursor, Claude, and other coding agents.
Use as project-level instruction context.

## 1) Project Goal

Deliver and maintain a local data platform sandbox for TechMart:
OLTP/Kafka/MinIO -> dbt (staging/vault/marts) -> Airflow orchestration -> Superset/Grafana BI and monitoring.

Primary business scope in this repo:
- Sales and customer analytics
- Business KPI marts (`business_kpis`)
- Operational BI dashboards

## 2) Core Principles

1. Make minimal, targeted changes.
2. Do not modify unrelated files.
3. Preserve existing architecture and naming conventions.
4. Prefer extending current pipelines over introducing parallel logic.
5. Keep docs synchronized with code changes.
6. Explicitly mark data limitations (do not fake missing metrics).

## 3) Architecture Pointers

Use these paths first:
- `dbt/` - transformation layers and tests
- `pipelines/` - Airflow DAGs, datasets contracts
- `configs/pipeline/` - runtime config (`dbt_rest.yaml`)
- `configs/app/` - Superset bootstrap/config
- `infra/monitoring/grafana/` - Grafana dashboards and provisioning
- `docs/` - project and runbook documentation

Do not duplicate architecture explanations in code comments; link docs instead.

## 4) Conventions

### SQL / dbt
- Keep naming style consistent: `stg_*`, `fct_*`, `dim_*`, `mart_*`.
- Use tags intentionally (`staging`, `vault`, `marts`, `business_kpis`).
- Add/adjust schema tests when creating marts.
- Use explicit NULL placeholders for unavailable data (e.g., CAC/ROAS if attribution is absent).

### Airflow
- Keep DAGs single-purpose and composable.
- Reuse dataset contracts from `pipelines/utils/datasets.py`.
- Reuse dbt-run abstraction from existing transformation DAG patterns.

### Superset / Grafana
- Extend existing bootstrap/provisioning flows.
- Keep dashboard updates idempotent where possible.
- Avoid duplicating the same deep analytics in both tools:
  - Superset = primary business analysis
  - Grafana = signal/operational KPI visibility

### Docs
- Update only relevant docs.
- Prefer links over duplicate prose.
- Keep instructions executable and short.

## 5) Safety Rules

Never:
- Rename or restructure major directories without explicit request.
- Remove existing metrics/dashboards unless explicitly asked.
- Invent data fields that do not exist in sources/models.
- Hide data gaps behind fabricated defaults.

Always:
- Validate assumptions against current models/sources.
- Keep backward-compatible slugs/UIDs where already used.
- Mention limitations when a metric is partial/gap by design.

## 6) How to Work with This Repo

Recommended execution order for business KPI work:
1. Check sources and existing marts.
2. Implement/extend dbt marts and tests.
3. Wire Airflow DAG/config for execution.
4. Wire Superset datasets/charts/dashboard.
5. Wire Grafana dashboard panels (signal-level).
6. Update docs and references.

## 7) Critical Anchors (current)

- dbt selector tag: `business_kpis`
- Airflow DAG: `dag_dbt_business_kpis_rest`
- Superset slug: `techmart-business-metrics-kpis`
- Grafana dashboard UID: `business-kpis`

## 8) Source of Truth Docs

Read these before major changes:
- `docs/PROJECT_SUMMARY.md`
- `docs/BUSINESS_METRICS.md`
- `docs/SUPERSET_BUSINESS_DASHBOARDS.md`
- `docs/PIPELINES.md`
- `docs/README.md`

If guidance conflicts, prefer concrete code + runbook behavior over narrative docs, then update docs.
