# Настройка

## Требования

- Docker и Docker Compose
- Python 3.11+
- (Опционально) Node.js 20+ для пересборки `services/dbt_web/frontend`

## Окружение

1. Скопируйте `.env.example` в `.env` и заполните значения.
2. Из корня репозитория (`DataOpsShowcase/`) запустите стек:
   - `docker compose up -d`

## Ingress (единая точка входа)

После запуска доступен nginx ingress:

- URL: `http://localhost:8090` (или `${INGRESS_PORT}` из `.env`)
- Маршруты:
  - `http://localhost:8090/dbt-web/`
  - `http://localhost:8090/dbt-api/v1/health`
  - `http://localhost:8090/airflow/`
  - `http://localhost:8090/mlflow/`
  - `http://localhost:8090/grafana/`

Подробная памятка по URL и credentials:

- [Web UI Access -> WEB_UI_ACCESS.md](WEB_UI_ACCESS.md)

## Airflow

- DAG: `pipelines/dags/`
- Connections: `configs/airflow/connections.json` (импорт в `airflow_init`)

## dbt

- Проект: `dbt/`
- Профили: `dbt/profiles.yml` (`DBT_PROFILES_DIR`)

## Локальные тесты

```bash
cd DataOpsShowcase
pip install -r requirements/dev.txt
pytest tests/unit
```

## CI

- `.github/workflows/dbt-docs.yml` — dbt parse/compile/docs + публикация артефактов.
- `.github/workflows/dbt-web.yml` — проверки backend/frontend dbt-web.
