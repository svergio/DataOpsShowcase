# Пустые дашборды Superset: дебаг ELT через Airflow

Цель: убедиться, что витрины есть **в той же БД и схеме**, куда смотрит Superset, затем повторить bootstrap.

Источник истины по датасетам: [`configs/app/superset_bootstrap.py`](../../configs/app/superset_bootstrap.py) (`DW_SCHEMA=dwh_marts`, список `TABLES`). Подключение OLAP в compose: `SUPERSET_DWH_DATABASE_URI` → `postgres_olap`, БД `PG_OLAP_DB` (по умолчанию `techmart_dwh`). Общий чек-лист DAG: [`AIRFLOW_DAG_TROUBLESHOOTING.md`](AIRFLOW_DAG_TROUBLESHOOTING.md).

**Приоритет дебага ELT для пустых чартов:** сначала **ingestion** (в т.ч. Kafka) и **`dag_spark_preprocess_to_stg`** — без стабильного raw и чистого staging цепочка до marts обычно не даёт консистентных витрин. **Atlas** и интеграционные DAG каталога **не блокируют** появление `dwh_marts.*`. Режим Airflow Variable **`spark_preprocess_mode`**: `any_raw` (OR по raw) удобен для dev/быстрых тестов и даёт риск неполного среза; подробнее — [`PIPELINES.md`](../PIPELINES.md) и раздел про Spark preprocess в [`AIRFLOW_DAG_TROUBLESHOOTING.md`](AIRFLOW_DAG_TROUBLESHOOTING.md).

## 0. Совпадение DSN и наличие таблиц

Частая ошибка: данные смотрят в **`postgres_dwh`** (raw/staging из runbook), а Superset — в **`postgres_olap`** / `techmart_dwh` / `dwh_marts`.

1. Проверьте в [`docker-compose.yml`](../../docker-compose.yml) переменные `SUPERSET_DWH_DATABASE_URI` у сервисов `superset` / `superset_init` и `PG_OLAP_*` в `.env`.
2. Выполните SQL **внутри OLAP-контейнера** (тот же хост/БД, что у URI):

```bash
cd /path/to/DataOpsShowcase
./scripts/verify_olap_marts_for_superset.sh
```

Или вручную:

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'dwh_marts'
  AND table_name IN (
    'fct_daily_sales','fct_orders','fct_payments',
    'dim_customers','dim_products',
    'redis_serving_snapshot','spark_analytics'
  )
ORDER BY 1,2;
```

Если строк нет или не хватает имён — проблема в ELT (Airflow/dbt/serving), не в UI Superset.

## 1. Гигиена Airflow и dbt REST

```bash
docker compose ps
docker compose logs airflow_scheduler --tail 200
docker compose logs dbt_rest --tail 200
```

Имена сервисов из [`docker-compose.yml`](../../docker-compose.yml): `airflow_scheduler`, `dbt_rest` (контейнер может называться `dbt-rest`).

В UI Airflow: откройте проблемный прогон → **Graph** / **Grid** → найдите первую задачу **failed** (не подменяйте корнем только `upstream_failed`). Лог первой failed — первичная причина.

Снимок последних прогонов по API: [`scripts/airflow_last_runs.py`](../../scripts/airflow_last_runs.py) (см. пример в [`AIRFLOW_DAG_TROUBLESHOOTING.md`](AIRFLOW_DAG_TROUBLESHOOTING.md)).

## 2. Цепочка до `dwh_marts` (OLAP для Product / Business / Customer дашбордов)

Нужен **success** у **`dag_dbt_marts_rest`** и обновлённый dataset **`dbt_marts_done`** (см. mermaid и таблицы в [`AIRFLOW_DAG_TROUBLESHOOTING.md`](AIRFLOW_DAG_TROUBLESHOOTING.md)).

Порядок проверки сверху вниз:

| Шаг | DAG | Файл |
|-----|-----|------|
| 1 | Ingestion `dag_ingest_*` | [`pipelines/dags/ingestion/`](../../pipelines/dags/ingestion/) |
| 2 | `dag_spark_preprocess_to_stg` | [`spark_preprocess_to_stg.py`](../../pipelines/dags/transformation/spark_preprocess_to_stg.py) |
| 3 | `dag_load_datavault`, `dag_scd2_satellites` | [`load_datavault.py`](../../pipelines/dags/transformation/load_datavault.py), [`scd2_satellites.py`](../../pipelines/dags/transformation/scd2_satellites.py) |
| 4 | `dag_dbt_staging_rest` → `dag_dbt_vault_rest` → **`dag_dbt_marts_rest`** | [`dbt_staging_rest.py`](../../pipelines/dags/transformation/dbt_staging_rest.py), [`dbt_vault_rest.py`](../../pipelines/dags/transformation/dbt_vault_rest.py), [`dbt_marts_rest.py`](../../pipelines/dags/transformation/dbt_marts_rest.py) |
| 5 | `dag_dbt_dqc_rest` (сигнал целостности) | [`dbt_dqc_rest.py`](../../pipelines/dags/transformation/dbt_dqc_rest.py) |

Если в DQC ошибки `relation does not exist` — сначала добейте **marts** (раздел 4 основного runbook).

Порядок только по dbt-слою из репозитория: [`pipelines/tools/airflow_run_dags_sequence.py`](../../pipelines/tools/airflow_run_dags_sequence.py).

## 3. Redis snapshot и Spark (чарты на Business / Customer дашбордах)

Чарты по Redis и Spark появляются после materialization таблиц; повторный `superset_bootstrap.py` подтянет датасеты (`fetch_metadata`) и обновит дашборды.

| Таблица | DAG | Задача / примечание |
|---------|-----|---------------------|
| `redis_serving_snapshot` | `dag_serving_optimizations` | `materialize_redis_serving` — [`serving_optimizations.py`](../../pipelines/dags/maintenance/serving_optimizations.py); dbt-модель [`redis_serving_snapshot`](../../dbt/models/marts/redis_serving_snapshot.sql) |
| `spark_analytics` | `dag_spark_analytics_to_marts` | [`spark_analytics_to_marts.py`](../../pipelines/dags/transformation/spark_analytics_to_marts.py); job [`spark/jobs/analytics_summary.py`](../../spark/jobs/analytics_summary.py) читает JDBC с `dwh_marts` |

Пока таблиц нет, соответствующие чарты на дашборде не создаются (остаётся markdown, если нет ни одной витрины для дашборда).

## 4. Superset после появления таблиц

```bash
docker compose exec superset python /app/pythonpath/superset_bootstrap.py
```

Bootstrap **обновляет** существующие дашборды по slug (раскладка и слайсы). После появления таблиц в OLAP достаточно снова выполнить команду ниже.

Открывайте дашборды по **slug**, а не по умолчанию `/superset/dashboard/1/`: `/superset/dashboard/techmart-business-overview/`, `/superset/dashboard/techmart-product-analytics/`, `/superset/dashboard/techmart-customer-sales-analysis/`.

## Критерий готовности

- Запрос из шага 0 возвращает нужные строки в `dwh_marts`.
- `dag_dbt_marts_rest` (и при необходимости upstream) — **success**.
- При необходимости Redis/Spark — success DAG из шага 3.
- `superset_bootstrap` без `Table … could not be found` для ожидаемых таблиц.
