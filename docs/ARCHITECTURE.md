# Архитектура DataOpsShowcase

Проект — **монорепозиторий** с едиными соглашениями по путям, конфигам и документации. Ниже — роли каталогов и как компоненты сходятся в рантайме (Docker Compose).

## Структура репозитория

| Путь | Роль |
|------|------|
| `pipelines/` | Airflow: DAG, плагины, `datasets` |
| `services/` | Общий Python: хранилища, Kafka, логи, метрики; **dbt-web** — веб-UI |
| `services/dbt_web/` | **Flask**: JSON API + Jinja-шаблоны + статика (CSS/JS, lineage на D3). Отдельного Node-фронтенда в compose нет. |
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

- `docker compose` поднимает, среди прочего: PostgreSQL (роли OLTP/OLAP/meta), Kafka, MinIO, Spark, Airflow, MLflow, **dbt-web**, Prometheus, **ingress (nginx)**.
- В **Airflow** смонтированы `pipelines/`, `services/`, `spark/`, `ml/`, `generators/`, `configs/`, `dbt/`.
- **Spark** workers получают `spark/jobs` и `spark/conf`; `py_files` — общий runtime из `spark/common/`.
- **dbt-web** обслуживает UI по префиксу `/dbt-web` и API `/api/v1` за ingress (см. [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md), [API.md](API.md)).
- **Наблюдаемость**: JSON-логи, метрики Prometheus, дашборды Grafana (см. `infra/monitoring`).

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
