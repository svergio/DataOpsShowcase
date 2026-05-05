#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TIMEOUT_SEC="${GEN_READY_TIMEOUT_SEC:-180}"
BOOTSTRAP_SLEEP="${GEN_BOOTSTRAP_SLEEP:-45}"

set -a
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck source=/dev/null
  . "$ROOT/.env"
fi
set +a

PG_OLTP_USER="${PG_OLTP_USER:-oltp_user}"
PG_OLTP_DB="${PG_OLTP_DB:-techmart_oltp}"
KAFKA_TOPIC_ORDERS="${KAFKA_TOPIC_ORDERS:-techmart.events.orders}"
MINIO_BUCKET_RAW="${MINIO_BUCKET_RAW:-techmart-data}"

docker compose --profile generators up -d data_generator

echo "Waiting up to 120s for data_generator health..."
for _ in $(seq 1 60); do
  st=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' data_generator 2>/dev/null || echo unknown)
  if [[ "$st" == "healthy" ]]; then
    echo "data_generator healthy."
    break
  fi
  sleep 2
done

if ! docker exec data_generator test -f /tmp/generator.alive; then
  echo "WARN: /tmp/generator.alive missing yet; continuing." >&2
fi

echo "Bootstrap sleep ${BOOTSTRAP_SLEEP}s (MinIO batch ticks, Kafka fill)..."
sleep "$BOOTSTRAP_SLEEP"

oltp_ok=0
deadline=$((SECONDS + TIMEOUT_SEC))
while [[ $SECONDS -lt $deadline ]]; do
  cnt=$(docker exec postgres_oltp psql -U "$PG_OLTP_USER" -d "$PG_OLTP_DB" -tAc "SELECT COUNT(*) FROM orders;" 2>/dev/null || echo 0)
  if [[ "${cnt:-0}" =~ ^[1-9][0-9]*$ ]]; then
    echo "OK OLTP orders count=$cnt"
    oltp_ok=1
    break
  fi
  sleep 5
done
if [[ "$oltp_ok" -ne 1 ]]; then
  echo "FAIL: OLTP orders still empty after ${TIMEOUT_SEC}s" >&2
  exit 1
fi

kafka_ok=0
deadline=$((SECONDS + TIMEOUT_SEC))
while [[ $SECONDS -lt $deadline ]]; do
  off_out=$(docker exec kafka kafka-run-class kafka.tools.GetOffsetShell \
    --broker-list localhost:9092 --topic "$KAFKA_TOPIC_ORDERS" --time -1 2>/dev/null || true)
  max_off=0
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    off="${line##*:}"
    [[ "$off" =~ ^[0-9]+$ ]] || continue
    if [[ "$off" -gt "$max_off" ]]; then max_off="$off"; fi
  done <<< "$(printf '%s\n' "$off_out")"
  if [[ "$max_off" -gt 0 ]]; then
    echo "OK Kafka topic $KAFKA_TOPIC_ORDERS high-offset=$max_off"
    kafka_ok=1
    break
  fi
  sleep 5
done
if [[ "$kafka_ok" -ne 1 ]]; then
  echo "FAIL: Kafka topic $KAFKA_TOPIC_ORDERS has no messages after ${TIMEOUT_SEC}s" >&2
  exit 1
fi

NET=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{printf "%s" $k}}{{break}}{{end}}' postgres_olap 2>/dev/null || true)
if [[ -z "$NET" ]]; then
  echo "WARN: could not detect docker network from postgres_olap; skipping MinIO object check." >&2
else
  minio_live=0
  if docker run --rm --network "$NET" curlimages/curl:8.5.0 -sf "http://minio:9000/minio/health/live" >/dev/null 2>&1; then
    minio_live=1
  fi
  if [[ "$minio_live" -ne 1 ]]; then
    echo "FAIL: MinIO health/live unreachable" >&2
    exit 1
  fi
  echo "OK MinIO health/live"

  minio_obj_ok=0
  deadline=$((SECONDS + TIMEOUT_SEC))
  while [[ $SECONDS -lt $deadline ]]; do
    listing=$(docker run --rm --network "$NET" \
      -e "MINIO_ROOT_USER=${MINIO_ROOT_USER}" \
      -e "MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}" \
      -e "MINIO_BUCKET_RAW=${MINIO_BUCKET_RAW}" \
      --entrypoint /bin/sh \
      minio/mc:latest \
      -c 'mc alias set s3 http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1 && mc ls "s3/${MINIO_BUCKET_RAW}/raw/" 2>/dev/null | head -5' || true)
    if echo "$listing" | grep -q .; then
      echo "OK MinIO bucket ${MINIO_BUCKET_RAW}/raw/ has objects (sample):"
      echo "$listing"
      minio_obj_ok=1
      break
    fi
    sleep 8
  done
  if [[ "$minio_obj_ok" -ne 1 ]]; then
    echo "FAIL: no objects under s3/${MINIO_BUCKET_RAW}/raw/ after ${TIMEOUT_SEC}s" >&2
    exit 1
  fi
fi

echo "generators_wait_ready.sh finished OK."
