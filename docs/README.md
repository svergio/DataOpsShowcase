# Документация DataOpsShowcase

Вся документация ведётся **на русском** (единая терминология: dbt, Data Vault, Kafka, MinIO, Spark, Airflow). Начните с [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) или с [корневого README.md](../README.md).

## Оглавление

| Документ | Назначение |
|----------|------------|
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Глобальная сводка: песочница, стек, поток данных, типовые задачи |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Монорепозиторий, роли каталогов, интеграция в рантайме |
| [SETUP.md](SETUP.md) | Требования, Docker Compose, `.env`, тесты, CI |
| [API.md](API.md) | Базовые URL API, dbt-web, ингресс |
| [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) | Веб-интерфейсы, логины, прямые порты |
| [PIPELINES.md](PIPELINES.md) | Airflow DAG, datasets, конфиги в `configs/pipeline/` |
| [ML.md](ML.md) | Каталог `ml/`, Airflow, MLflow |
| [Generators.md](Generators.md) | Синтетические данные: Kafka, MinIO, OLTP |
| [Roadmap.md](Roadmap.md) | Дорожная карта: 15 идей (ETL/ML), P0–P2, платформа/DQ/observability |

## Материалы для бизнеса

| Путь | Назначение |
|------|------------|
| [business/README.md](business/README.md) | Вводный указатель |
| [business/overview.md](business/overview.md) | Что за песочница и зачем (простой язык) |
| [business/use_cases.md](business/use_cases.md) | 10 бизнес-сценариев |
| [business/value.md](business/value.md) | Польза: обучение, демо, путь к мини-продукту |

## Диаграммы

| Путь | Назначение |
|------|------------|
| [diagrams/README.md](diagrams/README.md) | Описание схем и как их открывать |
| [diagrams/dwh-schemas.md](diagrams/dwh-schemas.md) | **DWH: схемы PostgreSQL** (staging, vault, marts, meta) |
| [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md) | Поток Data Vault / слои dbt |
| [diagrams/oltp-er.md](diagrams/oltp-er.md) | OLTP (ER, Mermaid) |
| [diagrams/kafka-er.md](diagrams/kafka-er.md) | Топики Kafka (Mermaid) |
| [diagrams/minio-er.md](diagrams/minio-er.md) | Структура MinIO (Mermaid) |
