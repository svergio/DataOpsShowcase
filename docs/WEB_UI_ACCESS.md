# Доступ к веб-интерфейсам

Проект использует **единый nginx ingress** — единственная HTTP-точка для всех веб-UI в стеке (файл [`infra/ingress/nginx.conf`](../infra/ingress/nginx.conf)). Прямые порты на хост для Airflow, Grafana, Superset, Prometheus, Jupyter, Spark UI, MinIO Console и т.д. **не публикуются**; исключение для инфраструктуры: **S3 API MinIO** по `MINIO_PORT` (часто `9000`) и порты БД/брокера (Postgres, Kafka, Redis).

## Базовый URL

```text
http://localhost:${INGRESS_PORT}
```

Типичное значение: `INGRESS_PORT=8090` в `.env` и `INGRESS_BASE_URL=http://localhost:8090`. Все пути ниже относительны этой базы.

**Согласование с браузером.** Строка в адресной строке должна совпадать по схеме, хосту и порту с `INGRESS_BASE_URL`. Если открыть только `http://localhost/superset/...` без `:8090`, а в `.env` указан порт **8090**, куки и редиректы Superset/других приложений могут расходиться с конфигом (`SUPERSET_WEBSERVER_BASE_URL`). Выбор: всегда использовать канонический URL с тем же портом, что в `.env`, либо изменить `INGRESS_PORT` и `INGRESS_BASE_URL` под ваш проброс (например ingress на 80). Быстрая проверка ингресса с хоста: [`scripts/ingress_smoke.sh`](../scripts/ingress_smoke.sh).

**Терминология.** Ниже в таблице отдельно следует различать **полноценные веб-интерфейсы** (HTML в браузере) и **маршруты REST/API за тем же ingress** (ответы в основном JSON). Пути `/schema-registry/` и `/kafka-connect/` — **только REST**; они поднимаются вместе с основным `docker compose`.

## Таблица маршрутов

| Путь | Сервис |
|------|--------|
| `/` | Портал стека (Flask `portal_web`: ссылки и live-статусы контейнеров). Карточки и граф настраиваются в [`services/portal_web/data/catalog.json`](../services/portal_web/data/catalog.json) (см. [`services/portal_web/README.md`](../services/portal_web/README.md)). |
| `/dbt/` | **dbt Docs** — статический сайт после `dbt docs generate` (см. [API.md](API.md)) |
| `/dbt-web/…` | Постоянный редирект 301 на `/dbt/…` (совместимость закладок) |
| `/airflow/` | Airflow Web UI |
| `/mlflow/` | MLflow (уже `--static-prefix /mlflow`) |
| `/grafana/` | Grafana |
| `/superset/` | Apache Superset |
| `/jupyter/` | Jupyter Notebook / Lab (`NotebookApp.base_url=/jupyter/`) |
| `/prometheus/` | Prometheus UI (ингресс отрезает префикс до `prometheus:9090/`) |
| `/pushgateway/` | Prometheus Pushgateway |
| `/spark-master/` | Spark Master Web UI (`spark.master.ui.reverseProxy*` в `spark-defaults.conf`) |
| `/spark-worker/` | Spark Worker Web UI |
| `/minio-console/` | MinIO Console (**порт консоли 9001 только внутри сети**) |
| `/node-red/` | Node-RED editor и HTTP In nodes (`httpAdminRoot` / `httpNodeRoot` = `/node-red`; логин `NODE_RED_ADMIN_*` в `.env`) |
| `/atlas/` | Apache Atlas — веб-UI и API (старт контейнера может быть долгим; см. SETUP) |
| `/schema-registry/` | Confluent Schema Registry — **только REST** (JSON; не отдельный UI) |
| `/kafka-connect/` | Kafka Connect / Debezium — **только REST** (JSON) |
| `/nl2sql/` | NL2SQL HR (Flask UI + API): см. [`services/nl2sql_app/README.md`](../services/nl2sql_app/README.md), блок про MLflow ниже |

Подключение объектного хранилища с хоста: `http://localhost:${MINIO_PORT}` (обычно `9000`) — без префикса ingress.

**Согласование URL MinIO.** В [`docker-compose.yml`](../docker-compose.yml) по умолчанию: `MINIO_SERVER_URL=http://localhost:${MINIO_PORT}`, `MINIO_BROWSER_REDIRECT_URL=${INGRESS_BASE_URL}/minio-console/`. Если меняете `MINIO_PORT` или `INGRESS_PORT`/`INGRESS_BASE_URL`, скопируйте актуальные значения в `.env`, либо задайте `MINIO_BROWSER_REDIRECT_URL`/`MINIO_SERVER_URL` явно (см. [`.env.example`](../.env.example)).

## Кратко по основным приложениям

### dbt Docs (статика)

| Параметр | Значение |
|----------|----------|
| **URL** | `http://localhost:${INGRESS_PORT}/dbt/` |
| **Учётная запись** | Не требуется (статические файлы) |

Страница появляется после успешной генерации артефактов (**`dbt docs generate`**), в compose обычно из DAG `dag_dbt_marts_rest` (задача `docs`). До этого **`/dbt/`** может отвечать ошибкой — см. [API.md](API.md).

### Airflow / MLflow / Grafana

| Сервис | URL за ingress | Учётные данные |
|--------|----------------|----------------|
| **Airflow** | `${INGRESS_BASE_URL}/airflow/` | Из `.env`: `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` (в [`.env.example`](../.env.example) по умолчанию `admin` / `admin`) |
| **Node-RED** | `${INGRESS_BASE_URL}/node-red/` | `NODE_RED_ADMIN_USER` / `NODE_RED_ADMIN_PASSWORD` (в `.env.example`: `admin` / `changeme`) |
| **MLflow** | `${INGRESS_BASE_URL}/mlflow/` | В типовом стенде UI **без входа**; URI трекинга внутри сети — `MLFLOW_TRACKING_URI` |
| **Grafana** | `${INGRESS_BASE_URL}/grafana/` | `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` (в `.env.example`: `admin` / `admin`) |

Дашборды и метаданные прогонов: [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md).

### NL2SQL (`/nl2sql/`)

После пересборки и перезапуска контейнера **`nl2sql_app`** страница **`http://localhost:${INGRESS_PORT}/nl2sql/`** должна открываться (**200**). Если артефакт MLflow ещё недоступен, на странице показывается **жёлтый блок** с текстом ошибки; **`GET ${INGRESS_BASE_URL}/nl2sql/health`** (на контейнере это **`/health`**) остаётся **`503` degraded**, пока проверка **`mlflow_model`** не проходит.

**Важно про MLflow UI.** Создать в реестре только **имя** модели (например **`nl2sql_qwen`** на странице Models) недостаточно: для URI вида **`models:/nl2sql_qwen/latest`** нужна **хотя бы одна зарегистрированная версия** (artifact из прогона или ручная регистрация). Пустой список versions в MLflow означает, что приложение по-прежнему не сможет загрузить модель.

Чтобы чат реально работал:

1. Зарегистрировать **версию** модели **`nl2sql_qwen`** в MLflow (не только пустую заготовку имени), либо  
2. Включить **`NL2SQL_AUTO_LOG_MODEL=true`** в `.env`, чтобы при старте сервис сам залогировал pyfunc-модель под именем из **`NL2SQL_MODEL_NAME`** (тяжёлый старт, нужны ресурсы и доступ к базовой модели).

При смене имени или stage правьте **`NL2SQL_MODEL_URI`** (см. [`.env.example`](../.env.example)).

### Запуск dbt и метаданные прогонов

HTTP API для запусков dbt — сервис **dbt-rest** (`dbt-rest:8580` внутри сети), не путать с HTML **dbt Docs**. Описание: [API.md](API.md).

## Быстрый старт

```text
http://localhost:8090/dbt/
http://localhost:8090/airflow/
http://localhost:8090/superset/
http://localhost:8090/minio-console/
http://localhost:8090/prometheus/
http://localhost:8090/atlas/
http://localhost:8090/node-red/
http://localhost:8090/nl2sql/
```

Пока **Atlas** или **Kafka Connect** ещё не готовы, запросы к `/atlas/`, `/schema-registry/` или `/kafka-connect/` могут кратко отвечать **502** от nginx — это ожидаемо в окне старта.

## Типовые неполадки

| Симптом | Что проверить |
|---------|----------------|
| **404** | Совпадает ли путь с `nginx.conf` |
| **502 на `/` после пересоздания контейнеров** | В [`infra/ingress/nginx.conf`](../infra/ingress/nginx.conf) upstream задаётся через **переменную в `proxy_pass`** и **resolver `127.0.0.11`**, чтобы Docker DNS подтягивал новый IP без перезапуска nginx. Если 502 сохраняется: `docker compose exec ingress nginx -s reload` или `docker compose restart ingress`; логи `portal_web` и `dataops_ingress`. |
| **502 на `/atlas/` или CDC** | Логи `atlas_server` / `schema_registry` / `debezium_connect`; Atlas долго выходит на порт 21000 |
| **Прямое подключение к старым портам** | Порты веб-сервисов закрыты; используйте `INGRESS_PORT` или `MINIO_PORT` только для S3 |
| **`/nl2sql/` открывается, но жёлтый блок / чат не работает** | В MLflow у **`nl2sql_qwen`** должна быть **версия**, не только созданное имя модели; либо **`NL2SQL_AUTO_LOG_MODEL=true`**. Логи: `docker logs nl2sql_app`. |
| **Пустой контент Superset, редирект на `/superset/superset/...`** | Открывайте только **`/superset/dashboard/...`** (один сегмент `superset`); базовый URL совпадает с `INGRESS_BASE_URL`. См. [SUPERSET.md](SUPERSET.md); nginx редиректит двойной префикс (`infra/ingress/nginx.conf`). |

## См. также

- [SETUP.md](SETUP.md) — первый запуск
- [ARCHITECTURE_ATLAS.md](ARCHITECTURE_ATLAS.md), [ARCHITECTURE_CDC.md](ARCHITECTURE_CDC.md) — Atlas и CDC за ingress
