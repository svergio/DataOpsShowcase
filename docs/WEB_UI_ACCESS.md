# Доступ к веб-интерфейсам

Проект открывает несколько веб-UI через **единый nginx ingress** (см. [API.md](API.md) и `infra/ingress/nginx.conf`).

## Базовый URL

```text
http://localhost:${INGRESS_PORT}
```

Типичное значение: `INGRESS_PORT=8090` в `.env`. Все пути ниже **относительны** этой базы, если не указано иное.

## Список интерфейсов

### dbt-web (Flask)

| Параметр | Значение |
|----------|----------|
| **URL** | `http://localhost:${INGRESS_PORT}/dbt-web/` |
| **Назначение** | Просмотр runs, моделей, тестов, docs, **lineage** (D3), артефакты |
| **Вход** | Сессия: `http://localhost:${INGRESS_PORT}/dbt-web/login` — логин/пароль по умолчанию из `DBT_WEB_AUTH_USER` / `DBT_WEB_AUTH_PASSWORD` (часто `admin` / `admin`) |

**Важно:** отдельного контейнера «React-фронтенд» в compose **нет** — одно Flask-приложение (Jinja + статика).

### Airflow

| Параметр | Значение |
|----------|----------|
| **URL** | `.../airflow/` |
| **Назначение** | Мониторинг DAG, ручной запуск, логи задач |
| **Учётка** | `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` из `.env` |

### MLflow

| Параметр | Значение |
|----------|----------|
| **URL** | `.../mlflow/` |
| **Назначение** | Эксперименты, метрики, артефакты моделей |
| **Auth** | В учебном стенде обычно **без** обязательной аутентификации (см. `docker-compose`) |

### Grafana

| Параметр | Значение |
|----------|----------|
| **URL** | `.../grafana/` |
| **Назначение** | Дашборды, метрики, лаги (по настройке) |
| **Учётка** | `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` |

### API dbt-web за ingress (тот же backend)

- База для проверок: `http://localhost:${INGRESS_PORT}/dbt-api/v1/`
- Пример: `.../dbt-api/v1/health`

Список эндпоинтов: [API.md](API.md). Токен для **отдельного** dbt REST (сервис `dbt-rest`), если используется: `DBT_REST_TOKEN` в `.env`.

## Где лежат учётки и порты

| Файл / источник | Что внутри |
|-----------------|------------|
| `.env` | Рабочие значения для локали |
| `.env.example` | Шаблон |
| `docker-compose.yml` | Проброс `ENV` в контейнеры |
| `infra/monitoring/grafana/provisioning/*` | Provisioning Grafana (учётка из env) |

Сопоставление:

- Airflow: `AIRFLOW_ADMIN_*`
- Grafana: `GRAFANA_ADMIN_*`
- dbt-web сессия: `DBT_WEB_AUTH_*` (и секрет `DBT_WEB_SECRET_KEY` в backend)

## Быстрый старт в браузере

```text
http://localhost:8090/dbt-web/
http://localhost:8090/airflow/
http://localhost:8090/mlflow/
http://localhost:8090/grafana/
http://localhost:8090/dbt-api/v1/health
```

(замените `8090` на ваш `INGRESS_PORT`).

## Прямой порт dbt-web (без nginx)

- С хоста: `http://localhost:${DBT_WEB_BACKEND_PORT}` (часто `8010` → `http://localhost:8010/dbt-web/`)

## Типовые неполадки

| Симптом | Что проверить |
|--------|----------------|
| **404** | Запущен ли `ingress`, совпадает ли путь с `nginx.conf` (`docker compose ps`) |
| **502** | Целевой сервис down или unhealthy; `docker compose ps`, логи |
| **Cannot login** | Значения в `.env` для Airflow/Grafana/dbt-web; после смены — `docker compose up -d --force-recreate <сервис>` |
| **401/403** на API | Токен `DBT_REST_TOKEN` (если требуется) для dbt REST, не путать с сессией dbt-web |

## См. также

- [SETUP.md](SETUP.md) — первый запуск
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) — зачем стенд
