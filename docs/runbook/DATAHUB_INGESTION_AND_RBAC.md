# DataHub Ingestion and RBAC

## Scope
Runbook for DataHub dual-run phase in `infrastructure/datahub`.

## Start services
```bash
make up
```

## Run ingestion
```bash
# Default recipe (Postgres OLAP)
make datahub-ingest

# Specific recipe
infrastructure/datahub/scripts/run-ingestion.sh infrastructure/datahub/ingestion/recipes/airflow_to_datahub.yml
```

## Recommended ingestion order
1. PostgreSQL schemas/tables/views (`postgres_olap_to_datahub.yml`).
2. Airflow DAG metadata (`airflow_to_datahub.yml`).
3. dbt lineage and model metadata (`dbt_to_datahub.yml`).

## RBAC guidance (dual-run)
- Keep `AUTH_ENABLED=false` only for local dev.
- For shared environments, enable auth and configure groups by domain:
  - `dataops-admins`: platform admins.
  - `analytics-engineers`: metadata editors.
  - `business-readers`: view-only consumers.
- Restrict ingestion credentials to service accounts only.

## Validation checklist
- DataHub UI opens on `${DATAHUB_PORT:-9002}`.
- Datasets from `staging`, `vault`, `marts`, `meta` are searchable.
- dbt model lineage links to upstream/downstream assets.
