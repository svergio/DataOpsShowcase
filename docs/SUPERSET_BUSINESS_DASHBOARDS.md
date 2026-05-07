# Бизнес-дашборды Superset (спека)

Реализация: [`configs/app/superset_bootstrap.py`](../configs/app/superset_bootstrap.py). Подключение **TechMart DWH** (Postgres), датасеты и дашборды **идемпотентны** (повторный запуск обновляет URI, `fetch_metadata`, слайсы и `position_json`). Для первых трёх дашбордов регистрируются таблицы: `dim_customers`, `dim_products`, `fct_orders`, `fct_daily_sales`, `redis_serving_snapshot`. Четвёртый дашборд использует ту же БД и схему **`demo_fin`** (таблицы появляются после Spark DAG `dag_spark_hive_finance_cbr_demo`).

| Slug | Назначение | Чарты (кратко) | Оркестрация данных |
|------|------------|----------------|----------------------|
| `techmart-business-overview` | Бизнес-обзор (RU) | KPI выручка / дней, линия продаж, bar валюта, Redis table+bar; при нехватке рядов — payment state / pie категорий | dbt marts + `dag_serving_optimizations` (Redis) |
| `techmart-product-analytics` | Продуктовая аналитика (RU) | KPI каталог, pie категорий, table каталога, line/bar продаж, bar payment state, pie сегментов клиентов, bar доменов email | dbt marts |
| `techmart-customer-sales-analysis` | Клиенты и продажи (RU) | KPI заказы/выручка, line заказов, bar payment, table заказов, area paid/unpaid, Redis bar, KPI клиентов / spend 90d, bar сегментов | dbt marts + serving |
| `techmart-business-metrics-kpis` | Расширенные бизнес-метрики (RU) | Top-line KPI (GMV/Net Revenue/AOV), retention line (D1/D7/D30/D90), category revenue, unit-economics table, marketing coverage table | `dag_dbt_business_kpis_rest` (или `dag_dbt_marts_rest`) |
| `techmart-finansy-hive-demo` | Финансы демо (RU) | KPI выручка RUB / заказы, линия RUB, bar по валюте, bar/pie mix заказов | `dag_spark_hive_finance_cbr_demo` после marts (SOAP ЦБ + JDBC в Postgres `demo_fin`; slug с «hive» — стабильность URL, **не** Apache Hive) |

## Демо финансов (`demo_fin`)

Таблицы **`demo_fin.mart_daily_finance_rub`** и **`demo_fin.mart_order_mix_rub`** создаёт Spark-job того же DAG в **`postgres_olap`** (`techmart_dwh`). Нужны **Spark master/worker** и **Airflow** для запуска DAG после **`dbt_marts_done`**.

Порядок для демо: **postgres_olap** (marts) → **`dag_spark_hive_finance_cbr_demo`** → при необходимости **`superset_init`** / повторный bootstrap.

После появления таблиц:

```bash
docker compose exec superset python /app/pythonpath/superset_bootstrap.py
```
