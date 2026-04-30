# Доступ к веб-интерфейсам

Проект использует **единый nginx ingress** — единственная HTTP-точка для всех веб-UI в стеке (файл [`infra/ingress/nginx.conf`](../infra/ingress/nginx.conf)). Прямые порты на хост для Airflow, Grafana, Superset, Prometheus, Jupyter, Spark UI, MinIO Console и т.д. **не публикуются**; исключение для инфраструктуры: **S3 API MinIO** по `MINIO_PORT` (часто `9000`) и порты БД/брокера (Postgres, Kafka, Redis).

## Базовый URL

```text
http://localhost:${INGRESS_PORT}
```

Типичное значение: `INGRESS_PORT=8090` в `.env` и `INGRESS_BASE_URL=http://localhost:8090`. Все пути ниже относительны этой базы.

**Терминология.** Ниже в таблице отдельно следует различать **полноценные веб-интерфейсы** (HTML в браузере) и **маршруты REST/API за тем же ingress** (ответы в основном JSON, без отдельного «веб-приложения» на уровне продукта). Пути `/schema-registry/` и `/kafka-connect/` относятся ко второму типу и доступны только при CDC-overlay.

## Таблица маршрутов

| Путь | Сервис |
|------|--------|
| `/` | Портал стека (Flask `portal_web`: ссылки и live-статусы контейнеров). Карточки и граф настраиваются в [`services/portal_web/data/catalog.json`](../services/portal_web/data/catalog.json) (см. [`services/portal_web/README.md`](../services/portal_web/README.md)). |
| `/dbt/` | dbt-web (Flask UI) |
| `/dbt-web/…` | Постоянный редирект 301 на `/dbt/…` (совместимость закладок) |
| `/api/`, `/dbt-api/` | тот же backend dbt-web |
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
| `/atlas/` | Apache Atlas — веб-UI и API (после overlay `infra/metadata/atlas/docker-compose.atlas.yml`) |
| `/schema-registry/` | Confluent Schema Registry — **только REST** (JSON; не отдельный UI), после overlay CDC |
| `/kafka-connect/` | Kafka Connect / Debezium — **только REST** (JSON), после overlay CDC |

Подключение объектного хранилища с хоста: `http://localhost:${MINIO_PORT}` (обычно `9000`) — без префикса ingress.

**Согласование URL MinIO.** В [`docker-compose.yml`](../docker-compose.yml) по умолчанию: `MINIO_SERVER_URL=http://localhost:${MINIO_PORT}`, `MINIO_BROWSER_REDIRECT_URL=${INGRESS_BASE_URL}/minio-console/`. Если меняете `MINIO_PORT` или `INGRESS_PORT`/`INGRESS_BASE_URL`, скопируйте актуальные значения в `.env`, либо задайте `MINIO_BROWSER_REDIRECT_URL`/`MINIO_SERVER_URL` явно (см. [`.env.example`](../.env.example)).

## Кратко по основным приложениям

### dbt-web (Flask)

| Параметр | Значение |
|----------|----------|
| **URL** | `http://localhost:${INGRESS_PORT}/dbt/` |
| **Логин** | `DBT_WEB_AUTH_USER` / `DBT_WEB_AUTH_PASSWORD` |

### Airflow / MLflow / Grafana

| Сервис | URL за ingress | Учётные данные |
|--------|----------------|----------------|
| **Airflow** | `${INGRESS_BASE_URL}/airflow/` | Из `.env`: `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` (в [`.env.example`](../.env.example) по умолчанию `admin` / `admin`) |
| **MLflow** | `${INGRESS_BASE_URL}/mlflow/` | В типовом стенде UI **без входа**; URI трекинга внутри сети — `MLFLOW_TRACKING_URI` |
| **Grafana** | `${INGRESS_BASE_URL}/grafana/` | `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` (в `.env.example`: `admin` / `admin`) |

Дашборды и метаданные прогонов: [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md).

### API dbt-web

- Здоровье: `${INGRESS_BASE_URL}/dbt-api/v1/health`
- Список API: [API.md](API.md)

## Быстрый старт

```text
http://localhost:8090/dbt/
http://localhost:8090/airflow/
http://localhost:8090/superset/
http://localhost:8090/minio-console/
http://localhost:8090/prometheus/
http://localhost:8090/atlas/
```

После включения overlays Atlas и CDC используйте те же базовые префиксы; пока контейнеры не подняты, запрос к `/atlas/`, `/schema-registry/` или `/kafka-connect/` вернёт 502 от nginx — это ожидаемо.

## Типовые неполадки

| Симптом | Что проверить |
|---------|----------------|
| **404** | Совпадает ли путь с `nginx.conf` |
| **502 на `/` после пересоздания `portal_web`** | Nginx мог кратко держать старый IP контейнера в DNS-кэше: подождать **до ~5 с** или выполнить `docker compose restart ingress`. При длительном 502 проверить логи `portal_web` и `dataops_ingress`. |
| **502 на /atlas/ или CDC** | Поднят ли overlay с `atlas_server` / `schema_registry` / `debezium_connect` на `dataops_net` |
| **Прямое подключение к старым портам** | Порты веб-сервисов закрыты; используйте `INGRESS_PORT` или `MINIO_PORT` только для S3 |

## См. также

- [SETUP.md](SETUP.md) — первый запуск
- [ARCHITECTURE_ATLAS.md](ARCHITECTURE_ATLAS.md), [ARCHITECTURE_CDC.md](ARCHITECTURE_CDC.md) — Atlas и CDC за ingress
