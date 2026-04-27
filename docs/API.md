# API и точки подключения

Этот файл отвечает на вопрос: **к какому API подключаться и по каким адресам**.

## 1) Основные API

- **dbt-web Backend API**
  - Внутри Docker-сети: `http://dbt-web-backend:8010`
  - С хоста (порт из `.env`): `http://localhost:8010`
  - OpenAPI: `services/dbt_web/openapi/dbt_web.openapi.yaml`

- **dbt-rest API** (сервис запуска dbt)
  - Внутри Docker-сети: `http://dbt-rest:8580`
  - База URL задается в `.env`: `DBT_REST_BASE_URL`
  - Используется Airflow и dbt-web backend

## 2) Полезные endpoint dbt-web

- `GET /api/v1/health` — healthcheck
- `GET /api/v1/runs` — список запусков
- `GET /api/v1/tests/summary` — сводка тестов
- `GET /api/v1/lineage` — граф lineage
- `POST /api/v1/docs/refresh` — обновить docs артефакты
- Webhooks от Airflow:
  - `POST /api/v1/events/ingestion_completed`
  - `POST /api/v1/events/datavault_completed`
  - `POST /api/v1/events/marts_completed`

## 3) Единая точка входа через Ingress

Добавлен сервис `ingress` (nginx) в `docker-compose.yml`.

- URL: `http://localhost:${INGRESS_PORT}` (по умолчанию `http://localhost:8090`)
- Маршруты:
  - `/dbt-web/` -> `dbt-web-frontend`
  - `/api/v1/...` -> `dbt-web-backend` (нужен для SPA: браузер зовет `/api/...` с того же origin)
  - `/dbt-api/v1/...` -> `dbt-web-backend/api/v1/...`
  - `/airflow/` -> Airflow Web UI
  - `/mlflow/` -> MLflow UI
  - `/grafana/` -> Grafana UI

Примеры:

- `http://localhost:8090/dbt-web/`
- `http://localhost:8090/dbt-api/v1/health`
- `http://localhost:8090/airflow/`

## 4) Где смотреть настройки

- Переменные окружения: `.env`, `.env.example`
- Ingress-конфиг: `infra/ingress/nginx.conf`
- Compose wiring: `docker-compose.yml`
