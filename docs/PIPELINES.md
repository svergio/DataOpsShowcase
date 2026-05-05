# Airflow: DAG и цепочка данных

В проекте **17** Airflow DAG, связанных через **Datasets** (события вместо жёсткого `ExternalTaskSensor` там, где настроено). Цепочка: ingestion, Spark-препроцессинг, загрузка **Data Vault**, SCD2, слои **dbt** (через dbt REST), **полный прогон dbt-тестов (DQC)**, Python data quality, serving, Spark serving analytics, демо **Spark + Postgres OLAP (`demo_fin`) + курсы ЦБ** после marts и обучение в Spark с **MLflow**.

Сводка стека и бизнес-образ: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md). Схема dbt: [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md). Диагностика падений и dataset-цепочки: [runbook/AIRFLOW_DAG_TROUBLESHOOTING.md](runbook/AIRFLOW_DAG_TROUBLESHOOTING.md). Пустые дашборды Superset и витрины `dwh_marts` в OLAP: [runbook/SUPERSET_EMPTY_DASHBOARDS_ELT.md](runbook/SUPERSET_EMPTY_DASHBOARDS_ELT.md).

Корень ingress (`/` на порту `INGRESS_PORT`, по умолчанию 8090) — **Flask-портал** (`portal_web`): обзор маршрутов, C4-подобная диаграмма и индикаторы состояния контейнеров (Docker + health + HTTP probe). JSON: `GET /api/status` (отдельный exact-location в nginx). **dbt Docs** (статика из `dbt/target/`) открываются по **`/dbt/`** (`/dbt-web/` редиректит сюда). В портале блок «API и внутренняя сеть» перечисляет в том числе **REST за ingress** (`/schema-registry/`, `/kafka-connect/`, **`/airflow/api/v1/`** — только JSON/health, при CDC-overlay) и внутренние хосты без префикса; см. [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) и [API.md](API.md).

**Скрипты стенда** (из корня репозитория, с заполненным `.env`): сброс тома OLAP и `dbt debug` — [`scripts/olap_fresh_volume.sh`](../scripts/olap_fresh_volume.sh) (`--dry-run`, `--yes`, `--skip-down`); после правок `infra/ingress/nginx.conf` и `catalog.json` — пересборка портала и ingress: [`scripts/ingress_portal_reload.sh`](../scripts/ingress_portal_reload.sh); проверка генератора (OLTP/Kafka/MinIO): [`scripts/generators_wait_ready.sh`](../scripts/generators_wait_ready.sh); оркестрация: [`scripts/stand_refresh.sh`](../scripts/stand_refresh.sh) (`--olap-only`, `--ingress-only`, `--generators`, `--airflow-sequence` в конце, остальные аргументы уходят в `airflow_run_dags_sequence.py`). Быстрая проверка ingress: [`scripts/smoke_ingress.sh`](../scripts/smoke_ingress.sh).

## Архитектура верхнего уровня

```mermaid
flowchart LR
  oltp[dag_ingest_oltp_to_stg]
  k_orders[dag_ingest_kafka_orders_to_raw]
  k_payments[dag_ingest_kafka_payments_to_raw]
  k_ext[dag_ingest_kafka_extensions_to_raw]
  minio_files[dag_ingest_minio_files_to_raw]

  spark[dag_spark_preprocess_to_stg]
  vault_load[dag_load_datavault]
  scd2[dag_scd2_satellites]

  dbt_stg[dag_dbt_staging_rest]
  dbt_vault[dag_dbt_vault_rest]
  dbt_marts[dag_dbt_marts_rest]
  dbt_dqc[dag_dbt_dqc_rest]

  dq[dag_data_quality_checks]
  serving[dag_serving_optimizations]
  spark_analytics[dag_spark_analytics_to_marts]
  spark_pg_finance[dag_spark_hive_finance_cbr_demo]
  mltrain[dag_ml_train_spark]

  oltp --> spark
  k_orders --> spark
  k_payments --> spark
  minio_files --> spark
  k_ext -.->|extensions -> dbt vault| dbt_vault
  spark --> vault_load --> scd2 --> dbt_stg --> dbt_vault --> dbt_marts --> dbt_dqc --> dq --> serving --> spark_analytics
  dbt_marts --> spark_pg_finance
  dbt_marts --> mltrain
```

Таблица **`raw.kafka_extension_events`** пополняется **`dag_ingest_kafka_extensions_to_raw`**; dbt-модели (`stg_extension_kafka_events`, hubs/satellites vault) опираются на raw. **`dag_dbt_vault_rest`** подписан на **`DS_DBT_STAGING_DONE | DS_RAW_KAFKA_EXTENSIONS`**: полная цепочка идёт через Spark, Python Vault и SCD2; при появлении только extensions запускается **dbt vault** без лишнего Python `dag_load_datavault`.

**`dag_spark_preprocess_to_stg`** — Airflow Variable **`spark_preprocess_mode`**: `all_raw` (по умолчанию) = **AND** по четырём raw Dataset; `any_raw` = **OR** (dev/тесты, риск неполного среза). PII остаётся в **raw**; после Spark **`staging.stg_customers`** и downstream dbt используют **`customer_hash`** и **`masked_*`**. Соль: **`SPARK_PRIVACY_SALT`** (compose / `.env`). Задания Spark: [`configs/pipeline/spark_jobs.yaml`](../configs/pipeline/spark_jobs.yaml).

## Каталог DAG

| # | DAG | Слой | Источник | Расписание | Outlet | Примечание |
|---|---|---|---|---|---|---|
| 1 | `dag_ingest_oltp_to_stg` | ingestion | OLTP Postgres | `*/15 * * * *` | `raw_oltp` | Watermark по таблицам |
| 2 | `dag_ingest_kafka_orders_to_raw` | ingestion | Kafka `orders` | `*/5 * * * *` | `raw_kafka_orders` | Micro-batch + offsets |
| 3 | `dag_ingest_kafka_payments_to_raw` | ingestion | Kafka `payments` | `*/5 * * * *` | `raw_kafka_payments` | Аналогично orders |
| 4 | `dag_ingest_minio_files_to_raw` | ingestion | MinIO objects | `*/15 * * * *` | `raw_minio_files` | Manifest + quarantine |
| 5 | `dag_ingest_kafka_extensions_to_raw` | ingestion | Kafka marketing/SEO/HR/features | `*/5 * * * *` | `raw_kafka_extensions` | Consolidator: частичные ошибки топиков допустимы при `min_success_count` в [`ingestion.yaml`](../configs/pipeline/ingestion.yaml) |
| 6 | `dag_spark_preprocess_to_stg` | preprocessing | raw -> stg (анонимизация) | Variable `spark_preprocess_mode`: **AND** (`all_raw`) или **OR** (`any_raw`) | `stg_clean` | См. [`spark_jobs.yaml`](../configs/pipeline/spark_jobs.yaml); соль `SPARK_PRIVACY_SALT` |
| 7 | `dag_load_datavault` | vault | stg -> hubs/links | `stg_clean` | `vault_loaded` | SHA-256 hash keys + idempotent upsert (customers/orders + link) |
| 8 | `dag_scd2_satellites` | vault | hubs -> sats | `vault_loaded` | `vault_scd2_done` | Python SCD2 + late arriving |
| 9 | `dag_dbt_staging_rest` | dbt | dbt run | `vault_scd2_done` | `dbt_staging_done` | REST trigger/polling |
| 10 | `dag_dbt_vault_rest` | dbt | dbt run | **ИЛИ** `dbt_staging_done` или `raw_kafka_extensions` | `dbt_vault_done` | Extensions: dbt vault без Python load_datavault |
| 11 | `dag_dbt_marts_rest` | dbt | dbt build | `dbt_vault_done` | `dbt_marts_done` | `tag:marts`; затем docs |
| 12 | `dag_dbt_dqc_rest` | dbt | dbt test | `dbt_marts_done` | `dbt_dqc_done` | Селектор `dqc_all_tests` через [`dbt_rest.yaml`](../configs/pipeline/dbt_rest.yaml) |
| 13 | `dag_data_quality_checks` | quality | DQ | `dbt_dqc_done` | `dq_passed` | Python-инварианты + severity |
| 14 | `dag_serving_optimizations` | serving | marts | dataset-driven | `serving_optimized` | Index/VACUUM/REINDEX + Redis materialization (`dwh_marts.redis_serving_snapshot`) |
| 15 | `dag_spark_analytics_to_marts` | serving | Spark analytics | dataset-driven (`serving_optimized`) | `spark_analytics_done` | Пишет summary в MinIO (Parquet) и в `dwh_marts.spark_analytics` |
| 16 | `dag_spark_hive_finance_cbr_demo` | transformation | Spark + JDBC marts + SOAP ЦБ + JDBC в Postgres | `dbt_marts_done` | `spark_hive_finance_done` | Таблицы `demo_fin.*` в `postgres_olap` |
| 17 | `dag_ml_train_spark` | mlops | Spark + MLflow | dataset-driven | `ml_train_done` | Только `staging.stg_orders` / `dwh_staging.stg_orders` (без raw OLTP) |

## Watermarks и идемпотентность

- Watermarks ingestion DAG хранятся в `meta.pipeline_watermarks` (`pipeline_name`).
- OLTP: timestamp watermark по каждой таблице.
- Kafka: offsets по партициям в JSON, commit только после успешной вставки.
- MinIO: file manifest со статусами `discovered|loaded|quarantined`.
- Serving Redis: watermark `serving.redis` обновляется после dual-write (Redis + `dwh_marts.redis_serving_snapshot`).
- DV/SCD2: hash-key upsert через `ON CONFLICT`, повторный запуск безопасен.

## Наблюдаемость

- `meta.pipeline_runs` заполняется через `start_run` / `finish_run`.
- `meta.dq_results` хранит результаты DQ-проверок.
- Представления: `meta.v_pipeline_runs_recent`, `meta.v_pipeline_runs_summary`, `meta.v_dq_recent`.
- Логи: структурированный JSON (`services/common/logging_utils.JsonFormatter`).
- Отдельный контур DQC и чек-листы: [QUALITY_AND_MONITORING.md](QUALITY_AND_MONITORING.md); тесты dbt и запуск см. [TESTING_AND_DATA_QUALITY.md](TESTING_AND_DATA_QUALITY.md); Grafana и метаданные — [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md).

## Надёжность

- Ретраи по умолчанию: 3 + exponential backoff (5 -> 30 мин), см. `pipelines/utils/dag_factory.py`.
- Для dbt REST задан отдельный retry policy в `configs/pipeline/dbt_rest.yaml`.
- DQ DAG блокирует serving при `severity in (critical, error)`.

## Конфигурация

Основные конфиги расположены в `configs/pipeline/`:

- `dag_registry.yaml`
- `ingestion.yaml`
- `datavault.yaml`
- `dbt_rest.yaml`
- `schemas.yaml`
- `watermarks.yaml`
- `dq_checks.yaml`
- `serving.yaml`

В Airflow они доступны по пути `/opt/airflow/configs/pipeline` через `DATAOPS_CONFIG_DIR`.

## Критерии приёмки

- Все 17 DAG парсятся без import errors.
- Dataset-зависимости корректно отображаются в Airflow UI.
- Повторные ingestion-run не создают дублей в `raw.*`.
- `dag_load_datavault` и `dag_scd2_satellites` идемпотентны.
- `dag_data_quality_checks` блокирует serving при нарушениях.
- Каждая задача пишет результат в `meta.pipeline_runs`.
- Секреты читаются из env/connections, не захардкожены в коде.
