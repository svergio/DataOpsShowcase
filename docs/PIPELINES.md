# DataOps Showcase: source-oriented DAG

Этот документ описывает production-реализацию из 13 Airflow DAG, связанных через Datasets. Цепочка включает ingestion, Spark-препроцессинг, загрузку Data Vault, SCD2, dbt REST слои, data quality, serving и ML-обучение в Spark с логированием в MLflow.

## Архитектура верхнего уровня

```mermaid
flowchart LR
  oltp[dag_ingest_oltp_to_stg]
  k_orders[dag_ingest_kafka_orders_to_raw]
  k_payments[dag_ingest_kafka_payments_to_raw]
  minio_files[dag_ingest_minio_files_to_raw]

  spark[dag_spark_preprocess_to_stg]
  vault_load[dag_load_datavault]
  scd2[dag_scd2_satellites]

  dbt_stg[dag_dbt_staging_rest]
  dbt_vault[dag_dbt_vault_rest]
  dbt_marts[dag_dbt_marts_rest]

  dq[dag_data_quality_checks]
  serving[dag_serving_optimizations]
  mltrain[dag_ml_train_spark]

  oltp --> spark
  k_orders --> spark
  k_payments --> spark
  minio_files --> spark
  spark --> vault_load --> scd2 --> dbt_stg --> dbt_vault --> dbt_marts --> dq --> serving
  dbt_marts --> mltrain
```

Оркестрация выполняется через **Airflow Datasets** (без `ExternalTaskSensor`): продюсер публикует dataset event, downstream DAG запускается по `schedule=[Dataset(...)]`.

## Каталог DAG

| # | DAG | Слой | Источник | Расписание | Outlet | Примечание |
|---|---|---|---|---|---|---|
| 1 | `dag_ingest_oltp_to_stg` | ingestion | OLTP Postgres | `*/15 * * * *` | `raw_oltp` | Watermark по таблицам |
| 2 | `dag_ingest_kafka_orders_to_raw` | ingestion | Kafka `orders` | `*/5 * * * *` | `raw_kafka_orders` | Micro-batch + offsets |
| 3 | `dag_ingest_kafka_payments_to_raw` | ingestion | Kafka `payments` | `*/5 * * * *` | `raw_kafka_payments` | Аналогично orders |
| 4 | `dag_ingest_minio_files_to_raw` | ingestion | MinIO objects | `*/15 * * * *` | `raw_minio_files` | Manifest + quarantine |
| 5 | `dag_spark_preprocess_to_stg` | preprocessing | raw -> stg | dataset-driven | `stg_clean` | Очистка, дедуп, контроль схемы |
| 6 | `dag_load_datavault` | vault | stg -> hubs/links | dataset-driven | `vault_loaded` | SHA-256 hash keys + idempotent upsert |
| 7 | `dag_scd2_satellites` | vault | hubs -> sats | dataset-driven | `vault_scd2_done` | SCD2 + late arriving |
| 8 | `dag_dbt_staging_rest` | dbt | dbt run | dataset-driven | `dbt_staging_done` | REST trigger/polling |
| 9 | `dag_dbt_vault_rest` | dbt | dbt run | dataset-driven | `dbt_vault_done` | `tag:vault` |
| 10 | `dag_dbt_marts_rest` | dbt | dbt run | dataset-driven | `dbt_marts_done` | `tag:marts` |
| 11 | `dag_data_quality_checks` | quality | DQ | dataset-driven | `dq_passed` | Инварианты + severity |
| 12 | `dag_serving_optimizations` | serving | marts | dataset-driven | `serving_optimized` | Index/VACUUM/REINDEX |
| 13 | `dag_ml_train_spark` | mlops | Spark + MLflow | dataset-driven | `ml_train_done` | Обучение + registry |

## Watermarks и идемпотентность

- Watermarks ingestion DAG хранятся в `meta.pipeline_watermarks` (`pipeline_name`).
- OLTP: timestamp watermark по каждой таблице.
- Kafka: offsets по партициям в JSON, commit только после успешной вставки.
- MinIO: file manifest со статусами `discovered|loaded|quarantined`.
- DV/SCD2: hash-key upsert через `ON CONFLICT`, повторный запуск безопасен.

## Наблюдаемость

- `meta.pipeline_runs` заполняется через `start_run` / `finish_run`.
- `meta.dq_results` хранит результаты DQ-проверок.
- Представления: `meta.v_pipeline_runs_recent`, `meta.v_pipeline_runs_summary`, `meta.v_dq_recent`.
- Логи: структурированный JSON (`services/common/logging_utils.JsonFormatter`).

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

- Все 13 DAG парсятся без import errors.
- Dataset-зависимости корректно отображаются в Airflow UI.
- Повторные ingestion-run не создают дублей в `raw.*`.
- `dag_load_datavault` и `dag_scd2_satellites` идемпотентны.
- `dag_data_quality_checks` блокирует serving при нарушениях.
- Каждая задача пишет результат в `meta.pipeline_runs`.
- Секреты читаются из env/connections, не захардкожены в коде.
