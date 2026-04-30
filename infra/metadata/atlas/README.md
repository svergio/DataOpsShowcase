# Apache Atlas (основной сервис каталога)

Overlay поднимает `sburn/apache-atlas`; учётные данные часто `admin` / `admin`.

**Ingress:** доступ с браузера — через основной ingress (часто `8090->80`; при пробросе `80:80` также `http://localhost/atlas/`). См. [docs/WEB_UI_ACCESS.md](../../docs/WEB_UI_ACCESS.md), [docs/ATLAS_RUNBOOK.md](../../docs/ATLAS_RUNBOOK.md).

```bash
export ATLAS_EXTERNAL_NETWORK=dataopsshowcase_dataops_net
docker compose -f docker-compose.yml -f infra/metadata/atlas/docker-compose.atlas.yml up -d
```

Публикация сущностей (идемпотентно: существующие `qualifiedName` пропускаются по умолчанию):

```bash
pip install -r infra/metadata/atlas/requirements.txt
python infra/metadata/atlas/scripts/entity_publish.py \
  --atlas-base-url "${INGRESS_BASE_URL:-http://localhost:8090}/atlas" \
  infra/metadata/atlas/ingestion/kafka_topics_batch.yml
```

Отражение информационной схемы:

```bash
PG_REFLECT_DSN=postgresql://oltp_user:oltp_pass@localhost:${PG_OLTP_PORT:-5433}/techmart_oltp \
  python infra/metadata/atlas/scripts/postgres_reflect_to_yaml.py

PG_REFLECT_DSN=postgresql://oltp_user:oltp_pass@localhost:${PG_OLTP_PORT:-5433}/techmart_oltp \
  python infra/metadata/atlas/scripts/postgres_reflect_to_yaml.py --emit-entities hive --output /tmp/oltp_hive.yml
python infra/metadata/atlas/scripts/entity_publish.py \
  --atlas-base-url "${INGRESS_BASE_URL:-http://localhost:8090}/atlas" \
  /tmp/oltp_hive.yml
```

Топики из генераторов (`configs/generators/company.generator.json` + env `KAFKA_TOPIC_*`):

```bash
python infra/metadata/atlas/scripts/generators_inventory_to_atlas_yaml.py \
  --config configs/generators/company.generator.json \
  --output /tmp/atlas_gen_topics.yml
python infra/metadata/atlas/scripts/entity_publish.py \
  --atlas-base-url "${INGRESS_BASE_URL:-http://localhost:8090}/atlas" \
  /tmp/atlas_gen_topics.yml
```

Контракт имён: [docs/ATLAS_ENTITY_CONTRACT.md](../../docs/ATLAS_ENTITY_CONTRACT.md).

Проверка качества (Atlas API; экспозиция в Pushgateway при `PROMETHEUS_PUSHGATEWAY_URL` в Airflow):

```bash
python infra/metadata/atlas/scripts/atlas_quality_gates.py --atlas-base-url http://atlas_server:21000
```

Airflow DAG `atlas_metadata_sync`: см. [docs/ARCHITECTURE_ATLAS.md](../../docs/ARCHITECTURE_ATLAS.md) — режим `incremental` (lite), опция `skip_static_kafka` / `ATLAS_SKIP_STATIC_KAFKA`, конфиг ретраев.

Runbooks: [docs/ATLAS_RUNBOOK.md](../../docs/ATLAS_RUNBOOK.md), [docs/ARCHITECTURE_ATLAS.md](../../docs/ARCHITECTURE_ATLAS.md), CDC: [docs/ARCHITECTURE_CDC.md](../../docs/ARCHITECTURE_CDC.md).
