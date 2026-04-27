# Диаграммы (Mermaid)

Схемы в формате **Mermaid** (рендер в GitHub, GitLab, VS Code / Cursor). SQL-DDL **не** дублируется здесь целиком: для OLTP — [services/postgres/init/02_oltp_schema.sql](../../services/postgres/init/02_oltp_schema.sql), для **схем DWH** — [dwh-schemas.md](dwh-schemas.md) + [dbt/dbt_project.yml](../../dbt/dbt_project.yml).

## Список

| Тема | Файл |
|------|------|
| **DWH: схемы PostgreSQL** (staging, vault, marts, meta) | [dwh-schemas.md](dwh-schemas.md) |
| Поток Data Vault / dbt (слой за слоем) | [data_vault_flow.md](data_vault_flow.md) |
| OLTP (источник) | [oltp-er.md](oltp-er.md) |
| Kafka (топики) | [kafka-er.md](kafka-er.md) |
| MinIO (bucket) | [minio-er.md](minio-er.md) |

**DBML-файлы** в репозитории не ведутся; при необходимости схему можно перенести в [dbdiagram.io](https://dbdiagram.io/) вручную.

## См. также

- [../PROJECT_SUMMARY.md](../PROJECT_SUMMARY.md) — обзор платформы
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — структура репо
- [../PIPELINES.md](../PIPELINES.md) — что пишет Airflow/Spark **до** dbt
