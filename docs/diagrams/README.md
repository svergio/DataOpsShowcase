# Диаграммы (Mermaid)

Схемы в формате **Mermaid** (рендер в GitHub, GitLab, VS Code / Cursor). SQL-DDL **не** дублируется здесь целиком: для OLTP — [services/postgres/init/02_oltp_schema.sql](../../services/postgres/init/02_oltp_schema.sql), для **схем DWH** — [dwh-schemas.md](dwh-schemas.md) + [dbt/dbt_project.yml](../../dbt/dbt_project.yml).

**Два слоя:**

- **Платформа (контейнеры Docker, HTTP, оркестрация):** [c4-container.md](c4-container.md).
- **Данные (ER топиков, bucket, OLTP, слои DWH):** таблица ниже.

## Список

| Тема | Файл |
|------|------|
| **C4: контейнеры** compose, ingress, dbt-rest, NL2SQL, наблюдаемость | [c4-container.md](c4-container.md) |
| **Security trust zones** (границы доступа и контуры доверия) | [security_trust_zones.md](security_trust_zones.md) |
| **DWH: схемы PostgreSQL** (staging, vault, marts, meta) | [dwh-schemas.md](dwh-schemas.md) |
| Поток Data Vault / dbt (слой за слоем) | [data_vault_flow.md](data_vault_flow.md) |
| **CI/CD + release governance** (quality gates, rollout, rollback) | [cicd_release_governance_flow.md](cicd_release_governance_flow.md) |
| **Incident + SLO + runbook** (эскалация и RCA цикл) | [incident_slo_runbook_flow.md](incident_slo_runbook_flow.md) |
| OLTP (источник) | [oltp-er.md](oltp-er.md) |
| Kafka (топики) | [kafka-er.md](kafka-er.md) |
| MinIO (bucket) | [minio-er.md](minio-er.md) |

**DBML-файлы** в репозитории не ведутся; при необходимости схему можно перенести в [dbdiagram.io](https://dbdiagram.io/) вручную.

## См. также

- [c4-container.md](c4-container.md) — контейнеры и ingress (runtime)
- [../PROJECT_SUMMARY.md](../PROJECT_SUMMARY.md) — обзор платформы
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — структура репо
- [../PIPELINES.md](../PIPELINES.md) — что пишет Airflow/Spark **до** dbt
- [../QUALITY_AND_MONITORING.md](../QUALITY_AND_MONITORING.md) — эксплуатационные проверки
