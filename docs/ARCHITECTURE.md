# Архитектура DataOpsShowcase

Проект — **монорепозиторий** с едиными соглашениями по путям, конфигам и документации. Ниже — роли каталогов и как компоненты сходятся в рантайме (Docker Compose).

## Структура репозитория

| Путь | Роль |
|------|------|
| `pipelines/` | Airflow: DAG, плагины, `datasets` |
| `services/` | Общий Python: хранилища, Kafka, логи, метрики; **dbt-rest** — запуск dbt по HTTP |
| `spark/jobs/` | Точки входа Spark-задач |
| `spark/common/` | Утилиты (`lib_runtime`, `spark_session`), подключаются в job как `py_files` |
| `ml/training/` | Скрипты обучения (например, `train_order_value_model.py`) |
| `ml/configs/`, `ml/features/`, `ml/inference/`, `ml/models/` | ML-конфиги, фичи, вывод, артефакты |
| `generators/` | Синтетика: `generator.py`, `kafka/`, `common/` |
| `dbt/` | dbt: `models/` (staging, vault, marts, serving), тесты, макросы |
| `configs/` | YAML: пайплайны, Airflow, Spark |
| `infra/` | Init SQL, ingress (nginx), Grafana/Prometheus |
| `scripts/` | Вспомогательные CLI |
| `tests/` | Pytest |

Сводка назначения платформы: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md).

## Интеграция в рантайме (Docker)

- `docker compose` поднимает, среди прочего: PostgreSQL (роли OLTP/OLAP/meta), Kafka, MinIO, Spark, Airflow, MLflow, Prometheus, **ingress (nginx)**.
- В **Airflow** смонтированы `pipelines/`, `services/`, `spark/`, `ml/`, `generators/`, `configs/`, `dbt/`.
- **Spark** workers получают `spark/jobs` и `spark/conf`; `py_files` — общий runtime из `spark/common/`.
- **dbt Docs** по префиксу **`/dbt/`**: nginx отдаёт статику из смонтированного **`dbt/target/`** (после `dbt docs generate`). Запуск dbt — **Airflow** и **`dbt-rest`** (см. [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md), [API.md](API.md)).
- **Наблюдаемость**: JSON-логи, метрики Prometheus, дашборды Grafana — конфиги в [`infra/monitoring/`](../infra/monitoring/); см. также [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md) и [TESTING_AND_DATA_QUALITY.md](TESTING_AND_DATA_QUALITY.md) (отличие от dbt DQ).

## Поток данных (логически)

```text
OLTP, Kafka, MinIO
    -> ingestion (Airflow)
    -> raw / landing в БД
    -> Spark: препроцессинг -> staging
    -> загрузка Data Vault (hubs, links) -> SCD2 в satellites
    -> dbt: staging (views) + vault + marts + serving
    -> data quality, serving-оптимизации
    -> ML-обучение (Spark) -> MLflow
```

Схемы: [diagrams/dwh-schemas.md](diagrams/dwh-schemas.md) (схемы БД), [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md) (поток DV). Фактическая цепочка DAG: [PIPELINES.md](PIPELINES.md).

## См. также

- [SETUP.md](SETUP.md) — запуск
- [Generators.md](Generators.md) — источники данных
- [ARCHITECTURE_ATLAS.md](ARCHITECTURE_ATLAS.md) — Atlas (каталог), прямые порты vs ingress
- [ARCHITECTURE_CDC.md](ARCHITECTURE_CDC.md) — Debezium, Schema Registry, Spark CDC
