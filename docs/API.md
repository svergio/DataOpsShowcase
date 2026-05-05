# API и точки подключения

Кратко: **куда** ходить **изнутри Docker** и **с хоста** при локальном запуске. Полный маршрутизатор внешнего трафика — [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) (ingress).

## dbt Docs (статика)

Сайт из [`dbt docs generate`](https://docs.getdbt.com/reference/commands/cmd-docs): артефакты в [`dbt/target/`](../dbt/target), каталог монтируется в контейнер **ingress** только для чтения. Отдаётся по префиксу **`/dbt/`**; nginx подменяет в `index.html` абсолютные пути и настройки UI-router, чтобы приложение работало под подкаталогом. Пока не выполнен хотя бы один успешный `docs generate` (например через DAG `dag_dbt_marts_rest`, слой `docs`), **`/dbt/`** может отдавать пустой ответ или 404 — это ожидаемо.

JSON **manifest** / **catalog** браузер загружает как `manifest.json` и `catalog.json` относительно **`/dbt/`** (отдельного публичного «JSON API метаданных» через ingress нет).

## dbt REST (внешний запуск dbt)

Единственный HTTP API в compose для **запуска** dbt и **статуса/логов** прогонов.

- Сервис в [`docker-compose.yml`](../docker-compose.yml): **`dbt_rest`** (`container_name: dbt-rest`), порт **8580** только внутри сети compose. Реализация: [`services/dbt_rest/`](../services/dbt_rest/) (FastAPI, версия `dbt-core`/`dbt-postgres` = **`DBT_IMAGE_TAG`**). **`GET /health/live`** — всегда **`200`**, если процесс отвечает (без проверки БД; удобно для HTTP-probe «процесс жив»). **`GET /health`**: `200` и `"database":"ok"` при успешном `SELECT 1` к мета-БД; **`503`** если **`DBT_REST_DB_DSN`** не задан или PostgreSQL недоступен (удобно для Docker healthcheck). **`run_id`** в путях должен быть валидным UUID — иначе **`400`**. **Метаданные прогонов** (статус, время, имена артефактов, логи) хранятся в PostgreSQL **`postgres_metadb`**, БД **`${PG_META_DB}`** (схема `dbt_rest`); тела артефактов — в каталоге проекта **`dbt/target/runs/{run_id}/`** на смонтированном томе. Завершение прогона в БД делается с повторными попытками и резервным `UPDATE`, чтобы строка не зависала в **`running`** при временных сбоях Postgres.
- **Airflow** (клиент [`services/dbt_client/rest_client.py`](../services/dbt_client/rest_client.py)): **`POST /runs`** — тело `job`, `selectors`, `target` (профиль), `command`, `fail_on_test_failure` и т.д.; без непустого **`command`** требуется **непустой `selectors`** (иначе 400 — защита от прогона всего проекта). При типовом пути с `selectors` используется **`dbt build`**, при `fail_on_test_failure: false` добавляется **`--no-fail-fast`**. **`GET /runs/{id}`** — статус; **`GET /runs/{id}/logs`** — текст лога.
- URL: `http://dbt-rest:8580` или `http://dbt_rest:8580` (имя сервиса в compose; на сети также задаётся alias **`dbt-rest`**) или переопределение через **`DBT_REST_BASE_URL`** в `.env`. При непустом **`DBT_REST_TOKEN`** передавайте заголовок `Authorization: Bearer …` на все вызовы API.
- **Имя Docker-сети:** в compose задано логическое имя **`dataops_net`**. На хосте сеть обычно отображается как **`<имя_проекта>_dataops_net`** (см. `docker compose ls`, `docker network ls`); при подключении сторонних контейнеров используйте полное имя.

## Единая точка входа: ingress (nginx)

Файл: [infra/ingress/nginx.conf](../infra/ingress/nginx.conf). База: `http://localhost:${INGRESS_PORT}` (часто `8090`).

| Префикс | Назначение |
|---------|------------|
| `/dbt/` | Статический **dbt Docs** (после `dbt docs generate`) |
| `/dbt-web/…` | Редирект 301 на `/dbt/…` |
| `/airflow/` | Airflow Web UI |
| `/mlflow/` | MLflow UI |
| `/grafana/` | Grafana |
| `/superset/` | Apache Superset |
| `/jupyter/` | Jupyter Notebook / Lab (`base_url=/jupyter/`) |
| `/prometheus/` | Prometheus Web UI за nginx (бекенд без subpath на `prometheus:9090`) |
| `/pushgateway/` | Pushgateway |
| `/spark-master/` / `/spark-worker/` | Spark standalone UI |
| `/minio-console/` | Консоль MinIO (API S3 — порт `MINIO_PORT`) |
| `/atlas/` | Apache Atlas — веб-UI и REST/API |
| `/schema-registry/` | Schema Registry REST (JSON; не полноценный UI) |
| `/kafka-connect/` | Kafka Connect / Debezium REST (JSON) |
| `/node-red/` | Node-RED editor (см. `NODE_RED_ADMIN_*` в `.env`) |

Примеры:

```text
http://localhost:8090/dbt/
http://localhost:8090/airflow/
```

## Настройки

- Переменные: `.env`, шаблон `.env.example`
- **dbt-rest:** в compose задаётся **`DBT_REST_DB_DSN`** → `postgres_metadb` / `${PG_META_DB}`; локально см. комментарий к `DBT_REST_DB_DSN` в `.env.example`
- Сборка: [docker-compose.yml](../docker-compose.yml)

## См. также

- [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) — логины и разбор 404/502
- [PIPELINES.md](PIPELINES.md) — откуда вызываются job и генерация docs
