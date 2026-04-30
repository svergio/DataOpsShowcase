# Настройка и запуск

## Требования

- **Docker** и **Docker Compose** (V2, команда `docker compose`).
- **Python 3.11+** — для локальных тестов Python-сервисов (например, `services/dbt_web/backend`).

## Первый запуск

1. Скопируйте шаблон окружения:

   ```bash
   cp .env.example .env
   ```

2. При необходимости поправьте порты и публичные URL в `.env` (например `INGRESS_PORT`/`INGRESS_BASE_URL`, `MINIO_PORT` — см. блок MinIO и ingress в `.env.example`: `MINIO_BROWSER_REDIRECT_URL`/`MINIO_SERVER_URL` должны соответствовать выбранным портам).

3. Из корня репозитория `DataOpsShowcase/`:

   ```bash
   docker compose up -d
   ```

4. Откройте **ingress** (по умолчанию `http://localhost:8090`) и проверьте маршруты из [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md).

## Postgres OLTP: старый Docker-том и `marketing_campaigns` / расширения

Скрипты из [`services/postgres/init/`](../services/postgres/init) монтируются в `postgres_oltp` как [`/docker-entrypoint-initdb.d/`](https://hub.docker.com/_/postgres) и выполняются **только при первом** создании данных (пустой том). Если том `pg_oltp_data` уже существовал до появления файла [`02b_oltp_marketing_hr_finance.sql`](../services/postgres/init/02b_oltp_marketing_hr_finance.sql), таблицы расширений (marketing, SEO, HR, finance) в БД **не создаются**.

**Варианты:**

1. **Авто-применение при старте `data_generator`** (по умолчанию в `docker-compose.yml`): файлы `02b` и `02c` смонтированы в контейнер (`02b_...`, `02c_oltp_retail_legacy.sql`); для расширений применяется `02b` по `OLTP_EXTENSIONS_SQL`, затем **всегда** (при включённом OLTP) — `02c` с колонками ретейл-линии. Идемпотентно. Достаточно пересобрать/перезапустить генератор с актуальным репозиторием.

2. **Сброс данных OLTP** (если данные не нужны): `docker compose down` и удаление тома `pg_oltp_data` (или `docker compose down -v`, если допустимо для остальных сервисов), затем `docker compose up` — init-скрипты выполнятся заново.

3. **Вручную** выполнить SQL на живой базе: `psql` с тем же файлом [`02b_oltp_marketing_hr_finance.sql`](../services/postgres/init/02b_oltp_marketing_hr_finance.sql).

Отключить авто-DDL у генератора: `OLTP_EXTENSIONS_SQL=` (пусто) в окружении `data_generator`.

## Ingress

Nginx публикует единую точку входа: dbt-web, Airflow, MLflow, Grafana, проксирование API. Конфиг: [infra/ingress/nginx.conf](../infra/ingress/nginx.conf).

## Postgres MetaDB и dbt-rest

Метаданные прогонов **dbt-rest** (статус, время, список артефактов, логи) хранятся в **`postgres_metadb`**, база **`${PG_META_DB}`**, схема **`dbt_rest`** — см. [`07_dbt_rest.sql`](../services/postgres/init/07_dbt_rest.sql). При **первом** создании тома `pg_meta_data` скрипт подхватывается из `docker-entrypoint-initdb.d`. Если том уже существовал, при старте контейнера **`dbt-rest`** выполняется идемпотентное создание схемы/таблицы (`ensure_schema`). При необходимости примените SQL вручную из каталога `DataOpsShowcase/`:

```bash
docker compose exec -T postgres_metadb psql -U "${PG_META_USER}" -d "${PG_META_DB}" < services/postgres/init/07_dbt_rest.sql
```

## Airflow

- DAG: [pipelines/dags/](../pipelines/dags/)
- Подключения: [configs/airflow/](../configs/airflow/) (см. инициализацию `airflow_init` в compose)

## dbt

- Проект: [dbt/](../dbt/)
- Профили: `dbt/profiles.yml`, каталог `DBT_PROFILES_DIR` (см. compose)
- **dbt REST** (запуск из Airflow по HTTP): сервис **`dbt-rest`** в [`docker-compose.yml`](../docker-compose.yml), реализация в [`services/dbt_rest/`](../services/dbt_rest/); **`DBT_REST_DB_DSN`** в compose указывает на **`postgres_metadb`**; **`DBT_REST_BASE_URL`**, **`DBT_REST_TOKEN`** — см. [API.md](API.md)

## Локальные тесты (Python)

```bash
cd DataOpsShowcase
pip install pytest numpy 'psycopg[binary]'
pip install -r generators/requirements.txt
pytest tests/unit
```

По умолчанию в `pytest.ini` перечислены маркеры (`integration`). **Юнит-тесты генератора** живут в `tests/unit/test_generators_config.py`, `test_company_profile.py`, `test_domain_constants.py`, `test_generator_xml_config.py`; зависимости — [generators/requirements.txt](../generators/requirements.txt) плюс `pytest`. Карта всех семейств тестов и dbt DQ: [TESTING_AND_DATA_QUALITY.md](TESTING_AND_DATA_QUALITY.md).

**Интеграционные тесты** ([tests/integration/test_generator_connectivity.py](../tests/integration/test_generator_connectivity.py)): проверка доступности Postgres, Redis, Kafka и MinIO из хоста против поднятого `docker compose`. Помечены `@pytest.mark.integration`. Задайте переменные (пример для портов, проброшенных на localhost):

```bash
export GENERATOR_IT_OLTP_DSN=postgresql://user:pass@localhost:55432/techmart_oltp
export GENERATOR_IT_REDIS_URL=redis://localhost:6379/0
export GENERATOR_IT_KAFKA_BOOTSTRAP=localhost:9092
export GENERATOR_IT_MINIO_ENDPOINT=localhost:9000
export GENERATOR_IT_MINIO_ACCESS_KEY=minio
export GENERATOR_IT_MINIO_SECRET_KEY=minio123
# опционально HTTPS к MinIO:
# export GENERATOR_IT_MINIO_SECURE=true

pytest tests/integration -m integration -q
```

Если переменная для сервиса не задана, соответствующий тест **пропускается** (`skip`), а не падает.

Тесты **dbt-web** backend (без отдельного Node-сборщика в CI):

```bash
cd services/dbt_web/backend
pip install -r requirements.txt
pytest -q
```

## CI (GitHub Actions)

- `.github/workflows/dbt-docs.yml` — `dbt parse` / `compile` / `docs` и публикация артефактов
- `.github/workflows/dbt-web.yml` — проверки **backend** `services/dbt_web`

## Когда что-то не взводится

1. `docker compose ps` — поднят ли `ingress` и целевой сервис.
2. Логи: `docker compose logs <сервис> --tail=100`
3. Разбор типичных 404/502/логинов: [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md)

## См. также

- [API.md](API.md) — URL API
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) — обзор стенда
