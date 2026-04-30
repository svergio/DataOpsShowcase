# CDC (Debezium, Kafka, Schema Registry, Spark)

Логическое реплицирование включено для `postgres_oltp`, `postgres_olap` и `postgres_metadb`. Для **существующих томов** Postgres см. `services/postgres/cdc/README.md`.

## Ingress и CDC

Schema Registry и Kafka Connect (Debezium) проксируются основным ingress (пути `/schema-registry/` и `/kafka-connect/`): с точки зрения клиента это **REST API** (типично JSON), не отдельные «веб-консоли» уровня Grafana. Отдельные порты **`18081`** / **`18083` на хост не публикуются.**

| Сервис в Docker | Префикс на ingress |
|-----------------|--------------------|
| `schema_registry:8081` | `${INGRESS_BASE_URL}/schema-registry/` |
| `debezium_connect:8083` | `${INGRESS_BASE_URL}/kafka-connect/` |

Внутри контейнеров по-прежнему `http://schema_registry:8081` и `http://debezium_connect:8083`.

## Подъём CDC

```bash
export ATLAS_EXTERNAL_NETWORK=dataopsshowcase_dataops_net
docker compose -f docker-compose.yml -f infra/cdc/docker-compose.cdc.yml up -d
```

## Регистрация коннекторов (с хоста через ingress)

```bash
export BASE="${INGRESS_BASE_URL:-http://localhost:8090}"

curl -sS -X POST -H 'Content-Type: application/json' \
  --data @configs/debezium/connector-postgres-oltp.json \
  "${BASE}/kafka-connect/connectors"
```

Подробнее и примеры для остальных JSON: [`configs/debezium/README.md`](../configs/debezium/README.md).

Коннекторы используют JSON converters; переход на Avro + Schema Registry — отдельный шаг документации.

Проверка слотов Postgres:

```sql
SELECT slot_name, active, wal_status FROM pg_replication_slots;
```

## Spark Streaming

Из контейнера `spark_master`:

```bash
/opt/spark/bin/spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  /opt/spark/jobs/cdc_structured_stream.py \
  --bootstrap-servers kafka:9092 \
  --subscribe-pattern 'cdc_.*' \
  --starting-offsets earliest \
  --sink foreach_preview
```

`foreach_preview` замените на JDBC `foreachBatch` в схемы `cdc_*` на OLAP, не пересекая витрины dbt без согласования.

Spark Master / Worker UI: `${INGRESS_BASE_URL}/spark-master/`, `/spark-worker/`.

## Совместимость с dbt

См. исходный план разделения `cdc_*`-схем и `meta.*` в OLAP.

## Lineage для Atlas

Обновляйте YAML в `infra/metadata/atlas/ingestion/` после появления реальных топиков и коннекторов.
