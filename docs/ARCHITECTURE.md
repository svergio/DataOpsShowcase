# Архитектура

## Структура репозитория (монорепозиторий)

| Путь | Роль |
| --- | --- |
| `pipelines/` | Airflow DAG, plugins, datasets |
| `services/` | Общие Python-библиотеки: storage, Kafka, dbt client, логирование/метрики, конфиги сервисов |
| `services/dbt_web/` | UI для dbt-документации (FastAPI backend + React frontend) |
| `spark/jobs/` | Точки входа Spark-задач |
| `spark/common/` | Общие Spark/JDBC утилиты (`lib_runtime`, `spark_session`) |
| `ml/training/` | Скрипты обучения моделей (Spark + MLflow) |
| `ml/configs/`, `ml/features/`, `ml/inference/`, `ml/models/` | ML-конфиги и доменные директории |
| `generators/` | Генераторы синтетических данных (`common/`, `kafka/`, `generator.py`) |
| `dbt/` | dbt-проект: `staging/`, `vault/`, `marts/`, `serving/`, tests, macros |
| `configs/` | YAML-конфигурации пайплайнов, Airflow, Spark |
| `infra/` | Docker init SQL, мониторинг (Prometheus, Grafana) |
| `scripts/` | Вспомогательные CLI-скрипты |
| `tests/` | Pytest тесты |

## Интеграция в рантайме

- `docker-compose.yml` поднимает PostgreSQL (OLTP/OLAP/meta), Kafka, MinIO, Spark, Airflow, MLflow, dbt-web, Prometheus.
- Airflow монтирует `pipelines/`, `services/`, `spark/`, `ml/`, `generators/`, `configs/`, `dbt/`.
- Spark workers монтируют `spark/jobs` и `spark/conf`.
- SparkSubmit получает `lib_runtime.py` и `spark_session.py` через `py_files`.
- Наблюдаемость реализована через структурные JSON-логи и метрики Prometheus.

## Поток данных (упрощённо)

OLTP/Kafka/MinIO -> **raw** -> Spark препроцессинг -> **staging** -> Data Vault/dbt -> **marts** -> **serving**. ML-обучение читает подготовленные слои (предпочтительно marts).
