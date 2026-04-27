# Web UI Access

## 1. Overview

Проект публикует несколько web-интерфейсов через единый nginx ingress.

Базовая точка входа:

- `http://localhost:${INGRESS_PORT}`
- Текущее значение в `.env`: `INGRESS_PORT=8090`

---

## 2. Web Interfaces

### dbt Web UI

URL:

- `http://localhost:${INGRESS_PORT}/dbt-web/`

Назначение:

- просмотр dbt запусков;
- lineage;
- модели;
- тесты;
- docs.

Credentials:

- No authentication required.

---

### Airflow UI

URL:

- `http://localhost:${INGRESS_PORT}/airflow/`

Назначение:

- мониторинг DAG;
- ручные запуски;
- просмотр task logs.

Credentials:

- username: `${AIRFLOW_ADMIN_USER}` (в `.env` сейчас `admin`)
- password: `${AIRFLOW_ADMIN_PASSWORD}` (в `.env` сейчас `admin`)

---

### MLflow UI

URL:

- `http://localhost:${INGRESS_PORT}/mlflow/`

Назначение:

- эксперименты;
- модели;
- метрики обучения.

Credentials:

- No authentication required.

---

### Grafana

URL:

- `http://localhost:${INGRESS_PORT}/grafana/`

Назначение:

- monitoring dashboards;
- pipeline metrics;
- лаги и эксплуатационные метрики.

Credentials:

- username: `${GRAFANA_ADMIN_USER}` (в `.env` сейчас `admin`)
- password: `${GRAFANA_ADMIN_PASSWORD}` (в `.env` сейчас `admin`)

---

### dbt REST / API (browser/debug)

URL:

- `http://localhost:${INGRESS_PORT}/dbt-api/v1/`

Назначение:

- debug API;
- проверка endpoint'ов и состояния runs.

Auth:

- token: `${DBT_REST_TOKEN}` (берется из `.env`; по умолчанию пустой).

---

## 3. Where Credentials Are Stored

Основные файлы:

- `.env` — рабочие значения для локального запуска;
- `.env.example` — шаблон переменных;
- `docker-compose.yml` — где эти переменные прокидываются в контейнеры;
- `services/airflow/config/airflow.cfg` — конфиг Airflow (без логина/пароля админа; они создаются через env в `docker-compose.yml`);
- `infra/monitoring/grafana/provisioning/*` — provisioning Grafana (логин/пароль берутся из env в `docker-compose.yml`).

Связка переменных и сервисов:

- Airflow UI: `AIRFLOW_ADMIN_USER`, `AIRFLOW_ADMIN_PASSWORD`
- Grafana UI: `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`
- dbt REST API token: `DBT_REST_TOKEN`
- dbt-web webhook/API token (если включен): `DBT_WEB_TOKEN`

---

## 4. Environment Variables (Important)

- `INGRESS_PORT` — внешний порт ingress (`http://localhost:${INGRESS_PORT}`).
- `AIRFLOW_ADMIN_USER` — логин администратора Airflow.
- `AIRFLOW_ADMIN_PASSWORD` — пароль администратора Airflow.
- `GRAFANA_ADMIN_USER` — логин администратора Grafana.
- `GRAFANA_ADMIN_PASSWORD` — пароль администратора Grafana.
- `DBT_REST_TOKEN` — токен для dbt REST API (если включена проверка токена).

Примечание:

- В текущем `docker-compose.yml` используются переменные `AIRFLOW_ADMIN_USER`, `AIRFLOW_ADMIN_PASSWORD`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`.

---

## 5. Quick Start

### Open everything in browser

- dbt-web -> `http://localhost:${INGRESS_PORT}/dbt-web/`
- airflow -> `http://localhost:${INGRESS_PORT}/airflow/`
- mlflow -> `http://localhost:${INGRESS_PORT}/mlflow/`
- grafana -> `http://localhost:${INGRESS_PORT}/grafana/`
- dbt api -> `http://localhost:${INGRESS_PORT}/dbt-api/v1/health`

---

## 6. Troubleshooting

- **404**
  - ingress не запущен или маршрут отсутствует в `infra/ingress/nginx.conf`.
  - Проверка: `docker compose ps ingress`.

- **502**
  - целевой сервис не поднят или unhealthy.
  - Проверка: `docker compose ps`.

- **Cannot login**
  - неверные значения в `.env` для `AIRFLOW_ADMIN_*` или `GRAFANA_ADMIN_*`.
  - после смены переменных нужно пересоздать сервисы (`docker compose up -d --force-recreate ...`).

- **API 401/403**
  - неверный `DBT_REST_TOKEN` или отсутствует заголовок авторизации.
