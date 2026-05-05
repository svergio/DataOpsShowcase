# Apache Superset (OLAP dashboards)

Superset использует **PostgreSQL** для метаданных и OLAP-витрин; демо-дашборд финансов (`demo_fin.*`) читается из той же OLAP-базы, что и остальные бизнес-дашборды.

| Назначение | Хост Compose | База данных | Переменные |
|------------|----------------|-------------|------------|
| Метаданные Superset (чарты, дашборды, пользователи) | `postgres_metadb` | `SUPERSET_DB_NAME` (по умолчанию `superset`) | `SQLALCHEMY_DATABASE_URI`, `PG_META_*` из `.env` |
| DWH OLAP для датасетов | `postgres_olap` | `PG_OLAP_DB` (`techmart_dwh`) | `SUPERSET_DWH_DATABASE_URI` или сборка через `SUPERSET_DWH_*` / `PG_OLAP_*` |

Витрины для BI задаются моделями dbt в схеме **`dwh_marts`**. Схема **`demo_fin`** заполняется Airflow DAG `dag_spark_hive_finance_cbr_demo` (Spark + SOAP ЦБ + JDBC в Postgres). Обзор слоёв см. [diagrams/dwh-schemas.md](diagrams/dwh-schemas.md) и пайплайн [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md).

## Образ и драйвер

Контекст сборки — [services/superset/Dockerfile](services/superset/Dockerfile): базовый `apache/superset` + **`psycopg2-binary`** (Postgres) в venv.

В [configs/app/superset_config.py](configs/app/superset_config.py) задано **`LOAD_EXAMPLES = False`**, чтобы `superset init` не подмешивал демо-дашборды и не путал список с продуктовыми slug-дашбордами из bootstrap.

## Запуск

```bash
docker compose build superset_init
docker compose up -d postgres_metadb postgres_olap spark_master spark_worker superset_init superset
```

Для bootstrap нужны **postgres_olap** (витрины и при необходимости `demo_fin` после DAG) и при полном стеке — **Spark master/worker** для запуска DAG.

## Полный сброс метаданных Superset (recreate)

Используйте, если в UI падает дашборд (например `TypeError` в браузере), «сломались» native filters или датасеты в метаданных, и проще пересоздать Superset, не трогая OLAP:

```bash
./scripts/superset_full_reset.sh
```

Скрипт останавливает `superset`, удаляет БД `SUPERSET_DB_NAME` (по умолчанию `superset`) на `postgres_metadb`, заново выполняет `superset_init` и поднимает `superset`. Данные в `postgres_olap` не затрагиваются.

После сброса открывайте дашборды по slug **без** устаревших query-параметров вроде `native_filters_key=...` (старый ключ после пересоздания может ломать клиент).

Инициализация выполняет `superset db upgrade`, создаёт admin, `superset init`, затем [configs/app/superset_bootstrap.py](configs/app/superset_bootstrap.py): регистрируется подключение **TechMart DWH**, датасеты витрин `dwh_marts` (в т.ч. `dim_customers`, `redis_serving_snapshot`) и датасеты схемы **`demo_fin`** после появления таблиц (DAG `dag_spark_hive_finance_cbr_demo`).

Bootstrap **идемпотентно** поддерживает одно подключение DWH, датасеты и **четыре дашборда** (все на Postgres OLAP; спека — [SUPERSET_BUSINESS_DASHBOARDS.md](SUPERSET_BUSINESS_DASHBOARDS.md)): при повторном запуске обновляются URI, метаданные датасетов, слайсы и раскладка дашборда. Старые слайсы с префиксом `TM_` удаляются после миграции на `RU_*`.

Если таблицы в `postgres_olap` ещё не materialized, в Superset всё равно создаются **записи датасетов** (placeholder) с тем же `schema`/`table_name`, чтобы они отображались в списке Datasets; после `dag_dbt_marts_rest` повторный bootstrap вызовет `fetch_metadata()` и чарты начнут отдавать данные.

| Slug | Смысл | Источник в BI |
|------|--------|----------------|
| `techmart-business-overview` | Бизнес-обзор (RU): KPI, динамика продаж, валюта, Redis; без Spark | `fct_daily_sales`, `fct_orders`, `redis_serving_snapshot`, при нехватке рядов — `dim_products` |
| `techmart-product-analytics` | Продуктовая аналитика (RU) | `dim_products`, `dim_customers`, `fct_daily_sales`, `fct_orders` |
| `techmart-customer-sales-analysis` | Клиенты и продажи (RU) | `fct_orders`, `fct_daily_sales`, `redis_serving_snapshot`, `dim_customers` |
| `techmart-finansy-hive-demo` | Финансы демо (RU): курсы ЦБ + Spark + Postgres (`demo_fin`; slug «hive» только для стабильности URL) | `demo_fin.mart_daily_finance_rub`, `demo_fin.mart_order_mix_rub` (после `dag_spark_hive_finance_cbr_demo`) |

Если таблицы ещё не materialized, на дашборде остаётся только markdown до появления данных; после dbt/DAG повторный bootstrap **добавит чарты** без удаления slug. Не путайте с пустым **`/superset/dashboard/1/`** после `superset init`: дашборды открываются по **slug**, например `http://localhost:${INGRESS_PORT:-8090}/superset/dashboard/techmart-business-overview/`.

Повторный bootstrap без полного `superset_init` (после появления таблиц в OLAP):

```bash
docker compose exec superset python /app/pythonpath/superset_bootstrap.py
```

## URLs

| Способ | URL |
|--------|-----|
| Рекомендуется (единый вход) | `http://localhost:${INGRESS_PORT:-8090}/superset/` |
| Бизнес-обзор | `http://localhost:${INGRESS_PORT:-8090}/superset/dashboard/techmart-business-overview/` |
| Продуктовая аналитика | `http://localhost:${INGRESS_PORT:-8090}/superset/dashboard/techmart-product-analytics/` |
| Клиенты и продажи | `http://localhost:${INGRESS_PORT:-8090}/superset/dashboard/techmart-customer-sales-analysis/` |
| Финансы (демо Postgres / Spark / ЦБ) | `http://localhost:${INGRESS_PORT:-8090}/superset/dashboard/techmart-finansy-hive-demo/` |

Канонический путь после ingress — **`/superset/dashboard/...`** (один сегмент `superset`). URL вида **`/superset/superset/...`** (двойной префикс) даёт поломанный роутинг SPA: пустые колонки датасета в редакторе, «Empty query», ошибки загрузки datasource и `TypeError` в теме. Ingress перенаправляет такие запросы на правильный путь (`infra/ingress/nginx.conf`).

Отдельного проброса `SUPERSET_PORT` на хост для UI нет. Логин: `SUPERSET_ADMIN_USER` / `SUPERSET_ADMIN_PASSWORD`.

### Bootstrap и `json_metadata` дашбордов

Скрипт [`configs/app/superset_bootstrap.py`](configs/app/superset_bootstrap.py) при обновлении дашбордов задаёт `json_metadata` через `_dashboard_json_metadata`: из ранее сохранённого JSON переносятся только **`label_colors`** и **`map_label_colors`**. Поля **`chart_configuration`** и **`global_chart_configuration`** каждый раз сбрасываются в пустые объекты — это предотвращает краши SPA (например `undefined` у темы), но **ручные правки раскладки/конфигурации чартов в этих полях после следующего прогона bootstrap не сохранятся**. Для окружений, где дашборды правят в UI, не запускайте bootstrap против «живых» дашбордов без понимания этого эффекта; для продакшена ограничьте bootstrap CI/инициализацией.

## Примечания

- Дебаг цепочки Airflow/dbt, если в OLAP нет таблиц `dwh_marts.*`, а дашборды пустые: [runbook/SUPERSET_EMPTY_DASHBOARDS_ELT.md](runbook/SUPERSET_EMPTY_DASHBOARDS_ELT.md); скрипт проверки таблиц: `scripts/verify_olap_marts_for_superset.sh`.
- Первое развёртывание должно пробежать пайплайны и **dbt** по слою marts; иначе часть чартов не создаётся (останется только markdown на пустых дашбордах).
- Для чартов с Redis на overview и customer дашбордах нужен успешный `dag_serving_optimizations` (task `materialize_redis_serving`) и модель dbt `redis_serving_snapshot`.
- Демо-дашборд финансов: после `DS_DBT_MARTS_DONE` запустите DAG `dag_spark_hive_finance_cbr_demo` (писать в `demo_fin` в `postgres_olap`), затем повторный bootstrap при необходимости; отдельный URL-префикс не нужен — тот же ingress `/superset/`.
- Опционально: `dag_spark_analytics_to_marts` пишет `dwh_marts.spark_analytics` в Postgres; первые три дашборда на него не опираются.
- Метаданные на PostgreSQL заменили SQLite для стека; том `superset_home` сохранён для локальных файлов Superset при необходимости.
- Ingress проксирует с префиксом `/superset/` на upstream `.../superset/...` (см. `infra/ingress/nginx.conf`), иначе Superset получает путь без префикса и отдаёт 404 на `/superset/welcome/`.
- Подкаталог: `SUPERSET_APP_ROOT=/superset` в compose; `FLASK_APP_MUTATOR` в `configs/app/superset_config.py`: `Superset.route_base = ""` (иначе редирект `/superset/superset/welcome/`), плюс обёртка `redirect_to_login` для параметра `next` (в upstream Superset в `next` попадал только `request.path` без префикса, т.е. `/welcome/` вместо `/superset/welcome/`). Публичный URL: `SUPERSET_WEBSERVER_BASE_URL` с `/superset/`.
