# Debezium connectors (PostgreSQL)

Prerequisites: базовый стек, `infra/cdc/docker-compose.cdc.yml`, WAL на Postgres (см. [`docs/ARCHITECTURE_CDC.md`](../../docs/ARCHITECTURE_CDC.md)), bootstrap в [`services/postgres/cdc`](../../services/postgres/cdc).

Пароли в JSON должны совпадать с `DEBEZIUM_*` в `.env`.

## Ingress (единая точка)

С хоста запросы к Schema Registry и Connect идут через nginx:

- `$INGRESS_BASE_URL/schema-registry/` для REST реестра
- `$INGRESS_BASE_URL/kafka-connect/` для Kafka Connect REST (префикс снимает nginx перед `debezium_connect:8083`)

Задайте базу перед `curl`:

```bash
BASE="${INGRESS_BASE_URL:-http://localhost:8090}"
BASE="${BASE%/}"
```

Examples:

```bash
curl -sS "${BASE}/schema-registry/subjects" | jq '. | length'

curl -sS -X POST -H "Content-Type: application/json" \
  --data @configs/debezium/connector-postgres-oltp.json \
  "${BASE}/kafka-connect/connectors"

curl -sS -X POST -H "Content-Type: application/json" \
  --data @configs/debezium/connector-postgres-olap.json \
  "${BASE}/kafka-connect/connectors"

curl -sS -X POST -H "Content-Type: application/json" \
  --data @configs/debezium/connector-postgres-metadb-airflow.json \
  "${BASE}/kafka-connect/connectors"

curl -sS -X POST -H "Content-Type: application/json" \
  --data @configs/debezium/connector-postgres-metadb-superset.json \
  "${BASE}/kafka-connect/connectors"

curl -sS -X POST -H "Content-Type: application/json" \
  --data @configs/debezium/connector-postgres-metadb-mlflow.json \
  "${BASE}/kafka-connect/connectors"
```

## List / status

```bash
BASE="${INGRESS_BASE_URL:-http://localhost:8090}"
BASE="${BASE%/}"

curl -sS "${BASE}/kafka-connect/connectors" | jq .

curl -sS "${BASE}/kafka-connect/connectors/postgres-oltp/status" | jq .
```

Внутри Docker-сети прямые URL остаются `http://debezium_connect:8083/...`.
