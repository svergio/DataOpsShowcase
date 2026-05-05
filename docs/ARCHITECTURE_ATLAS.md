# Apache Atlas (каталог метаданных)

Сервис **`atlas_server`** входит в корневой [`docker-compose.yml`](../docker-compose.yml) вместе с REST-публикаторами в `infra/metadata/atlas/`.

## Ingress и Atlas

Каталог доступен через **единый вход**: `${INGRESS_BASE_URL}/atlas/` (см. [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md), [infra/ingress/nginx.conf](../infra/ingress/nginx.conf)). Публикация порта **`ATLAS_PORT` на хост не используется** — только прокси.

Внутри Docker-сети задачи могут звать **`http://atlas_server:21000/`** (см. `ATLAS_REST_URL` в [`docker-compose.yml`](../docker-compose.yml)). Запуск **`entity_publish`** из контейнера (CI) с хостовым URL `http://localhost:.../atlas` неверен — передавайте `http://atlas_server:21000` (без суффикса `/atlas`), либо пробрасывайте `host.docker.internal` на хост.

### Если UI ломается за nginx по пути `/atlas/`

На части образов Atlas UI и редиректы считают себя смонтированными в `/`, а не под подпутём. Симптомы: циклы редиректа, абсолютные ссылки без `/atlas/`, 404 на статике. Обход: вызывать API **напрямую** в сети Compose `http://atlas_server:21000` (как в Airflow) или вынести Atlas в отдельный override compose с публикацией порта на хост.

## Подъём стека

Из корня репозитория `DataOpsShowcase/`:

```bash
docker compose up -d
```

Atlas стартует долго (см. healthcheck `start_period` в compose). Файл [`infra/metadata/atlas/docker-compose.atlas.yml`](../infra/metadata/atlas/docker-compose.atlas.yml) legacy-пустой — не подключайте его вторым `-f`.

С хоста (браузер и скрипт `entity_publish`): `http://localhost:${INGRESS_PORT:-8090}/atlas/` (API: `/atlas/api/...`). Учётные данные образа часто `admin` / `admin`.

## Публикация сущностей из YAML

С хоста URL Atlas должен указывать на префикс ingress ( nginx снимает `/atlas` при прокси на контейнер ):

```bash
cd DataOpsShowcase
pip install -r infra/metadata/atlas/requirements.txt
python infra/metadata/atlas/scripts/entity_publish.py \
  --atlas-base-url "http://localhost:${INGRESS_PORT:-8090}/atlas" \
  infra/metadata/atlas/ingestion/postgres_oltp.yml

python infra/metadata/atlas/scripts/entity_publish.py \
  --atlas-base-url "http://localhost:${INGRESS_PORT:-8090}/atlas" \
  infra/metadata/atlas/ingestion/kafka_topics_batch.yml
```

Если образ не принимает путь через прокси, используйте внутренний URL из того же состава контейнеров: `http://atlas_server:21000/` (Docker).

### Инвентарь Postgres

```bash
pip install -r infra/metadata/atlas/requirements.txt
PG_REFLECT_DSN=postgresql://${PG_OLTP_USER}:${PG_OLTP_PASSWORD}@localhost:${PG_OLTP_PORT}/${PG_OLTP_DB} \
  python infra/metadata/atlas/scripts/postgres_reflect_to_yaml.py --output /tmp/oltp_reflect.yml
```

### Проверка Superset и Atlas

Superset доступен только за ingress:

```bash
python infra/metadata/atlas/scripts/superset_ingest.py \
  --superset-base-url "${INGRESS_BASE_URL:-http://localhost:8090}/superset/"

python infra/metadata/atlas/scripts/superset_ingest.py \
  --superset-base-url "${INGRESS_BASE_URL:-http://localhost:8090}/superset/" \
  --atlas-base-url "${INGRESS_BASE_URL:-http://localhost:8090}/atlas" \
  --yaml infra/metadata/atlas/ingestion/superset_lineage.yml
```

## Глоссарий и контракты

- Runbook: [ATLAS_RUNBOOK.md](ATLAS_RUNBOOK.md) (502, DNS/upstream, URLs).
- Контракт сущностей: [ATLAS_ENTITY_CONTRACT.md](ATLAS_ENTITY_CONTRACT.md).
- Качество каталога: `infra/metadata/atlas/scripts/atlas_quality_gates.py` (счётчики по coarse types: приоритет `approximateCount` из `search/basic`, иначе сумма по страницам с `limit`/`offset`; dup-check YAML; Pushgateway). Дашборд Grafana: `infra/monitoring/grafana/dashboards/atlas-catalog.json`, правила Prometheus: `infra/monitoring/prometheus-rules/atlas.yml`.

`infra/metadata/glossary/` — источники правки для управления терминологией перед импортом в каталог.

## Airflow

DAG `atlas_metadata_sync` (расписание каждые 6 ч) выполняет reflect Postgres в сущности Atlas с типами **`hive_db` / `hive_table`** (имена типов в каталоге Atlas для JDBC-зеркала Postgres; **не** Apache Hive metastore), генерацию топиков из `generators_inventory_to_atlas_yaml.py` (путь JSON задаётся `GENERATOR_CONFIG_JSON`), публикацию статических YAML (Kafka перед Spark lineage), опционально dbt manifest, затем `atlas_quality_gates` с ретраями.

**Режим `incremental`** (conf `{"mode": "incremental"}`): не выполняются reflect Postgres, dbt manifest и inventory генераторов; **по-прежнему публикуются все статические YAML из `ingestion/`** (кроме исключений ниже) и выполняются quality gates. Это «лёгкий» цикл синхронизации, а не дельта только изменённых сущностей. В логе отчёт завершается строкой `stage:end:ok mode=lite_incremental` (в полном режиме — `mode=full`).

**Статический Kafka YAML:** по умолчанию публикуются `kafka_topics_batch.yml` и `kafka_cdc_topics.yml`. Если топики покрыты только inventory генераторов, можно отключить дубли: conf `{"skip_static_kafka": true}` или переменная окружения `ATLAS_SKIP_STATIC_KAFKA=true` (тогда эти два файла не публикуются; убедитесь, что нужные топики есть в inventory).

Числовые параметры ретраев можно задать в conf DAG (`publish_retries`, `publish_retry_delay_sec`, `quality_retries`, `quality_retry_delay_sec`) или через env `ATLAS_PUBLISH_*` / `ATLAS_QUALITY_*`; пустые и невалидные значения дают безопасные дефолты.

DAG `atlas_cdc_integration_touchpoint` проверяет `ATLAS_REST_URL` (`http://atlas_server:21000/`) и `DEBEZIUM_CONNECT_HEALTH_URL` внутри сети. Убедитесь, что `atlas_server` и `debezium_connect` подняты (`docker compose ps`).

Airflow UI: `${INGRESS_BASE_URL}/airflow/`.
