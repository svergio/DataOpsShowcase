# API и точки подключения

Кратко: **куда** ходить **изнутри Docker** и **с хоста** при локальном запуске. Полный маршрутизатор внешнего трафика — [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) (ingress).

## dbt-web (Flask)

Один процесс: HTML-страницы, статика, JSON API.

| Куда | URL (пример) |
|------|----------------|
| Сеть compose | `http://dbt-web-backend:8010` |
| С хоста (порт из `.env`, по умолчанию) | `http://localhost:8010` |
| Через ingress (рекомендуется) | `http://localhost:${INGRESS_PORT}/dbt-web/` — UI, `.../dbt-api/v1/...` — тот же backend под префиксом для API |

- OpenAPI-спека: [services/dbt_web/openapi/dbt_web.openapi.yaml](../services/dbt_web/openapi/dbt_web.openapi.yaml)

### Типовые `GET/POST` (префикс `/api/v1` у самого контейнера; за nginx часто ` /dbt-api/v1` → проксирование на backend)

| Метод | Путь | Назначение |
|--------|------|------------|
| GET | `/api/v1/health` | Проверка живости |
| GET | `/api/v1/runs` | Список запусков dbt (метаданные) |
| GET | `/api/v1/models` | Список моделей (с фильтрами) |
| GET | `/api/v1/tests/summary` | Сводка по тестам |
| GET | `/api/v1/lineage` | Граф зависимостей (с query-параметрами) |
| POST | `/api/v1/docs/refresh` | Обновить артефакты документации (по настройке) |
| POST | `/api/v1/events/...` | Webhook-события от пайплайнов (если включены) |

## dbt REST (внешний запуск dbt)

Используется оркестратором, не путать с **dbt-web** (UI).

- Внутри сети: `http://dbt-rest:8580` (см. `docker-compose` и `DBT_REST_BASE_URL` в `.env`).

## Единая точка входа: ingress (nginx)

Файл: [infra/ingress/nginx.conf](../infra/ingress/nginx.conf). База: `http://localhost:${INGRESS_PORT}` (часто `8090`).

| Префикс | Назначение |
|---------|------------|
| `/dbt-web/` | UI dbt-web (сессия, страницы runs/models/lineage/…) |
| `/dbt-api/v1/…` | Тот же backend dbt-web: API (удобно для единого origin) |
| `/airflow/` | Airflow Web UI |
| `/mlflow/` | MLflow UI |
| `/grafana/` | Grafana |

Примеры:

```text
http://localhost:8090/dbt-web/
http://localhost:8090/dbt-api/v1/health
http://localhost:8090/airflow/
```

## Настройки

- Переменные: `.env`, шаблон `.env.example`
- Сборка: [docker-compose.yml](../docker-compose.yml)

## См. также

- [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) — логины и разбор 404/502
- [PIPELINES.md](PIPELINES.md) — откуда вызываются job и webhooks
