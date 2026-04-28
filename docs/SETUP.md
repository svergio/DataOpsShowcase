# Настройка и запуск

## Требования

- **Docker** и **Docker Compose** (V2, команда `docker compose`).
- **Python 3.11+** — для локальных тестов Python-сервисов (например, `services/dbt_web/backend`).

## Первый запуск

1. Скопируйте шаблон окружения:

   ```bash
   cp .env.example .env
   ```

2. При необходимости поправьте порты в `.env` (см. `INGRESS_PORT`, `DBT_WEB_BACKEND_PORT`).

3. Из корня репозитория `DataOpsShowcase/`:

   ```bash
   docker compose up -d
   ```

4. Откройте **ingress** (по умолчанию `http://localhost:8090`) и проверьте маршруты из [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md).

## Ingress

Nginx публикует единую точку входа: dbt-web, Airflow, MLflow, Grafana, проксирование API. Конфиг: [infra/ingress/nginx.conf](../infra/ingress/nginx.conf).

## Airflow

- DAG: [pipelines/dags/](../pipelines/dags/)
- Подключения: [configs/airflow/](../configs/airflow/) (см. инициализацию `airflow_init` в compose)

## dbt

- Проект: [dbt/](../dbt/)
- Профили: `dbt/profiles.yml`, каталог `DBT_PROFILES_DIR` (см. compose)

## Локальные тесты (Python)

```bash
cd DataOpsShowcase
pip install pytest numpy 'psycopg[binary]'
pip install -r generators/requirements.txt
pytest tests/unit
```

По умолчанию в `pytest.ini` перечислены маркеры (`integration`). **Юнит-тесты генератора** живут в `tests/unit/test_generators_config.py`, `test_company_profile.py`, `test_domain_constants.py`, `test_generator_xml_config.py`; зависимости — [generators/requirements.txt](../generators/requirements.txt) плюс `pytest`.

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
