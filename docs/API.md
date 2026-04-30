# API и точки подключения

Кратко: **куда** ходить **изнутри Docker** и **с хоста** при локальном запуске. Полный маршрутизатор внешнего трафика — [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) (ingress).

## dbt-web (Flask)

Один процесс: HTML-страницы, статика, JSON API.

| Куда | URL (пример) |
|------|----------------|
| Сеть compose | `http://dbt-web-backend:8010` |
| С хоста | Только через ingress: UI `http://localhost:${INGRESS_PORT}/dbt/`, API `.../dbt-api/v1/...` (прямой порт 8010 на хост не публикуется) |

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

Используется оркестратором и проксируется из **dbt-web**, не путать с HTML/UI того же dbt-web.

- Сервис в [`docker-compose.yml`](../docker-compose.yml): **`dbt-rest`** (`container_name: dbt-rest`), порт **8580** только внутри сети compose. Реализация: [`services/dbt_rest/`](../services/dbt_rest/) (FastAPI, версия `dbt-core`/`dbt-postgres` = **`DBT_IMAGE_TAG`**). **`GET /health`**: `200` и `"database":"ok"` при успешном `SELECT 1` к мета-БД; **`503`** если **`DBT_REST_DB_DSN`** не задан или PostgreSQL недоступен (удобно для Docker healthcheck). **`run_id`** в путях должен быть валидным UUID — иначе **`400`**. **Метаданные прогонов** (статус, время, имена артефактов, логи) хранятся в PostgreSQL **`postgres_metadb`**, БД **`${PG_META_DB}`** (схема `dbt_rest`); тела артефактов — в каталоге проекта **`dbt/target/runs/{run_id}/`** на смонтированном томе. Завершение прогона в БД делается с повторными попытками и резервным `UPDATE`, чтобы строка не зависала в **`running`** при временных сбоях Postgres.
- **Airflow** (клиент [`services/dbt_client/rest_client.py`](../services/dbt_client/rest_client.py)): **`POST /runs`** — тело `job`, `selectors`, `target` (профиль), `command`, `fail_on_test_failure` и т.д.; без непустого **`command`** требуется **непустой `selectors`** (иначе 400 — защита от прогона всего проекта). При типовом пути с `selectors` используется **`dbt build`**, при `fail_on_test_failure: false` добавляется **`--no-fail-fast`**. **`GET /runs/{id}`** — статус; **`GET /runs/{id}/logs`** — текст лога.
- **dbt-web backend** (клиент [`services/dbt_web/backend/app/clients/dbt_rest_client.py`](../services/dbt_web/backend/app/clients/dbt_rest_client.py) при `DBT_REST_BASE_URL=http://dbt-rest:8580`): **`POST /jobs/run/{staging|vault|marts}`** — тело JSON опционально (пустое тело допустимо); поля как `RunJobRequest` (selectors, vars, full_refresh, defer, fail_on_test_failure), по умолчанию селектор `tag:<слой>`; для `selectors` используется тот же **`dbt build`** / **`--no-fail-fast`**, что и у Airflow. **`GET /runs/{id}/status`**, **`GET /runs/{id}/logs`**, **`GET /artifacts/{id}/{manifest.json|catalog.json|run_results.json|graph.js}`** — для UI, обновления lineage/manifest в dbt-web; `catalog.json` и `graph.js` чаще появляются после `dbt docs generate` (DAG `dataops_docs`).
- URL: `http://dbt-rest:8580` или переопределение через **`DBT_REST_BASE_URL`** в `.env`. При непустом **`DBT_REST_TOKEN`** передавайте заголовок `Authorization: Bearer …` на все вызовы API.
- **Имя Docker-сети:** в compose задано логическое имя **`dataops_net`**. На хосте сеть обычно отображается как **`<имя_проекта>_dataops_net`** (см. `docker compose ls`, `docker network ls`); при подключении сторонних контейнеров используйте полное имя.

## Единая точка входа: ingress (nginx)

Файл: [infra/ingress/nginx.conf](../infra/ingress/nginx.conf). База: `http://localhost:${INGRESS_PORT}` (часто `8090`).

| Префикс | Назначение |
|---------|------------|
| `/dbt/` | UI dbt-web (сессия, страницы runs/models/lineage/…) |
| `/dbt-web/…` | Редирект 301 на `/dbt/…` |
| `/dbt-api/v1/…` | Тот же backend dbt-web: API (удобно для единого origin) |
| `/airflow/` | Airflow Web UI |
| `/mlflow/` | MLflow UI |
| `/grafana/` | Grafana |
| `/superset/` | Apache Superset |
| `/jupyter/` | Jupyter Notebook / Lab (`base_url=/jupyter/`) |
| `/prometheus/` | Prometheus Web UI за nginx (бекенд без subpath на `prometheus:9090`) |
| `/pushgateway/` | Pushgateway |
| `/spark-master/` / `/spark-worker/` | Spark standalone UI |
| `/minio-console/` | Консоль MinIO (API S3 — порт `MINIO_PORT`) |
| `/atlas/` | Apache Atlas — веб-UI и REST/API (overlay) |
| `/schema-registry/` | Schema Registry REST (JSON; не полноценный UI; CDC overlay) |
| `/kafka-connect/` | Kafka Connect / Debezium REST (JSON; CDC overlay) |

Примеры:

```text
http://localhost:8090/dbt/
http://localhost:8090/dbt-api/v1/health
http://localhost:8090/airflow/
```

## Настройки

- Переменные: `.env`, шаблон `.env.example`
- **dbt-rest:** в compose задаётся **`DBT_REST_DB_DSN`** → `postgres_metadb` / `${PG_META_DB}`; локально см. комментарий к `DBT_REST_DB_DSN` в `.env.example`
- Сборка: [docker-compose.yml](../docker-compose.yml)

## См. также

- [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) — логины и разбор 404/502
- [PIPELINES.md](PIPELINES.md) — откуда вызываются job и webhooks
