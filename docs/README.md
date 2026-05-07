# Документация DataOpsShowcase

Вся документация ведётся **на русском** (единая терминология: dbt, Data Vault, Kafka, MinIO, Spark, Airflow). Начните с [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) или с [корневого README.md](../README.md).

## Оглавление

| Документ | Назначение |
|----------|------------|
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Глобальная сводка: песочница, стек, поток данных, типовые задачи |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Монорепозиторий, роли каталогов, интеграция в рантайме |
| [SETUP.md](SETUP.md) | Требования, Docker Compose, `.env`, тесты, CI |
| [API.md](API.md) | Базовые URL API, dbt REST, dbt Docs за ингрессом |
| [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) | Веб-интерфейсы, логины, согласование `INGRESS_BASE_URL` и браузера |
| [PIPELINES.md](PIPELINES.md) | Airflow DAG, datasets, конфиги в `configs/pipeline/` |
| [runbook/AIRFLOW_DAG_TROUBLESHOOTING.md](runbook/AIRFLOW_DAG_TROUBLESHOOTING.md) | Чек-лист диагностики по каждому DAG, снимок прогонов через API |
| [SUPERSET.md](SUPERSET.md) | Superset (meta DB + OLAP), bootstrap дашбордов, метаданные `json_metadata` |
| [SUPERSET_BUSINESS_DASHBOARDS.md](SUPERSET_BUSINESS_DASHBOARDS.md) | Описание бизнес-дашбордов по slug |
| [BUSINESS_METRICS.md](BUSINESS_METRICS.md) | Словарь бизнес-метрик и матрица покрытия данных (`ready/partial/gap`) |
| [runbook/SUPERSET_EMPTY_DASHBOARDS_ELT.md](runbook/SUPERSET_EMPTY_DASHBOARDS_ELT.md) | Пустые дашборды: цепочка ELT и OLAP |
| [runbook/TOOLING_BASELINE_AUDIT.md](runbook/TOOLING_BASELINE_AUDIT.md) | Базовый аудит и точки интеграции rollout tooling |
| [runbook/VAULT_OPERATIONS.md](runbook/VAULT_OPERATIONS.md) | Инициализация, policy bootstrap и операции Vault |
| [runbook/LAKEFS_BRANCHING_AND_ROLLBACK.md](runbook/LAKEFS_BRANCHING_AND_ROLLBACK.md) | Branching модель и rollback в lakeFS |
| [runbook/DATAHUB_INGESTION_AND_RBAC.md](runbook/DATAHUB_INGESTION_AND_RBAC.md) | Ingestion recipes и RBAC guidance для DataHub |
| [runbook/ARGOCD_PROMOTION_FLOW.md](runbook/ARGOCD_PROMOTION_FLOW.md) | Promotion и rollback flow в ArgoCD |
| [TESTING_AND_DATA_QUALITY.md](TESTING_AND_DATA_QUALITY.md) | Pytest, dbt tests, DQ, `scripts/run_dqc.sh` |
| [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md) | Grafana, Prometheus, метаданные прогонов |
| [QUALITY_AND_MONITORING.md](QUALITY_AND_MONITORING.md) | Короткий индекс качества и наблюдаемости |
| [ML.md](ML.md) | Каталог `ml/`, Airflow, MLflow, сервис **NL2SQL** (`/nl2sql/`) |
| [Generators.md](Generators.md) | Синтетические данные: Kafka, MinIO, OLTP |
| [Roadmap.md](Roadmap.md) | Дорожная карта: идеи ETL/ML, приоритеты |
| [GAPS_AND_PRODUCTION_READINESS.md](GAPS_AND_PRODUCTION_READINESS.md) | Приоритизированные gap'ы до production-ready состояния |
| [FAQ.md](FAQ.md) | Короткие ответы для стейкхолдеров и инженеров |
| [TOOLING_ROLLOUT_CHECKLIST.md](TOOLING_ROLLOUT_CHECKLIST.md) | Чек-лист rollout по Vault/lakeFS/DataHub/ArgoCD |

## Скрипты проверки (хост)

| Скрипт | Назначение |
|--------|------------|
| [`../scripts/ingress_smoke.sh`](../scripts/ingress_smoke.sh) | Быстрый `curl` к порталу, `/superset/health`, `/nl2sql/health`, `/prometheus/-/healthy` через ingress (`INGRESS_BASE_URL` / `INGRESS_PORT`) |
| [`../scripts/run_dqc.sh`](../scripts/run_dqc.sh) | Прогон dbt DQ (см. TESTING_AND_DATA_QUALITY) |
| [`../infrastructure/vault/scripts/bootstrap-vault.sh`](../infrastructure/vault/scripts/bootstrap-vault.sh) | Dev bootstrap для Vault |
| [`../infrastructure/lakefs/scripts/bootstrap-lakefs.sh`](../infrastructure/lakefs/scripts/bootstrap-lakefs.sh) | Первичная настройка lakeFS repository/branch |
| [`../infrastructure/datahub/scripts/run-ingestion.sh`](../infrastructure/datahub/scripts/run-ingestion.sh) | Запуск DataHub ingestion recipes |
| [`../infrastructure/argocd/scripts/gitops-sync.sh`](../infrastructure/argocd/scripts/gitops-sync.sh) | Принудительный sync ArgoCD приложения |

## Материалы для бизнеса

| Путь | Назначение |
|------|------------|
| [business/README.md](business/README.md) | Вводный указатель |
| [business/overview.md](business/overview.md) | Что за песочница и зачем (простой язык) |
| [business/use_cases.md](business/use_cases.md) | Бизнес + операционные use-cases с KPI/acceptance criteria |
| [business/value.md](business/value.md) | Польза: обучение, демо, путь к мини-продукту |
| [business/platform_value.md](business/platform_value.md) | Бизнес-смысл портала и каталога |

## Диаграммы

| Путь | Назначение |
|------|------------|
| [diagrams/README.md](diagrams/README.md) | Описание схем и как их открывать |
| [diagrams/dwh-schemas.md](diagrams/dwh-schemas.md) | **DWH: схемы PostgreSQL** (staging, vault, marts, meta) |
| [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md) | Поток Data Vault / слои dbt |
| [diagrams/oltp-er.md](diagrams/oltp-er.md) | OLTP (ER, Mermaid) |
| [diagrams/kafka-er.md](diagrams/kafka-er.md) | Топики Kafka (Mermaid) |
| [diagrams/minio-er.md](diagrams/minio-er.md) | Структура MinIO (Mermaid) |
| [diagrams/c4-container.md](diagrams/c4-container.md) | C4 контейнеров |
| [diagrams/security_trust_zones.md](diagrams/security_trust_zones.md) | Security boundary и trust zones |
| [diagrams/cicd_release_governance_flow.md](diagrams/cicd_release_governance_flow.md) | CI/CD и управляемый релиз |
| [diagrams/incident_slo_runbook_flow.md](diagrams/incident_slo_runbook_flow.md) | Операционный цикл инцидента и SLO |

## Остальное

| Путь | Назначение |
|------|------------|
| [ARCHITECTURE_CDC.md](ARCHITECTURE_CDC.md), [ARCHITECTURE_ATLAS.md](ARCHITECTURE_ATLAS.md) | CDC и Atlas за ingress |
| [ATLAS_ENTITY_CONTRACT.md](ATLAS_ENTITY_CONTRACT.md), [ATLAS_RUNBOOK.md](ATLAS_RUNBOOK.md) | Контракты и runbook Atlas |
| [DV2_ENTITY_KEYS.md](DV2_ENTITY_KEYS.md) | Ключи сущностей Data Vault 2 |
| [`../services/nl2sql_app/README.md`](../services/nl2sql_app/README.md) | NL2SQL (UI/API за `/nl2sql/`) |
