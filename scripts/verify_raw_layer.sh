#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MIN_ROWS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --min-rows)
      MIN_ROWS="${2:?}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--min-rows N]"
      echo "  Print row counts for key raw.* tables and kafka pipeline watermarks on postgres_olap."
      echo "  If --min-rows N (N>0), exit 1 when any listed raw table has count < N."
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if ! docker compose ps --status running --quiet postgres_olap 2>/dev/null | grep -q .; then
  echo "postgres_olap is not running." >&2
  exit 1
fi

PSQL=(docker compose exec -T postgres_olap psql -U "${PG_OLAP_USER:-olap_user}" -d "${PG_OLAP_DB:-techmart_dwh}" -v ON_ERROR_STOP=1)

echo "=== raw row counts ==="
"${PSQL[@]}" -c "
SELECT 'raw.kafka_orders' AS tbl, count(*)::bigint AS n FROM raw.kafka_orders
UNION ALL SELECT 'raw.kafka_payments', count(*) FROM raw.kafka_payments
UNION ALL SELECT 'raw.oltp_orders', count(*) FROM raw.oltp_orders
UNION ALL SELECT 'raw.minio_files_landing', count(*) FROM raw.minio_files_landing
ORDER BY 1;
"

echo "=== meta.pipeline_watermarks (kafka.*) ==="
"${PSQL[@]}" -c "
SELECT pipeline_name, left(watermark_value, 120) AS watermark_preview
FROM meta.pipeline_watermarks
WHERE pipeline_name LIKE 'kafka.%'
ORDER BY 1;
" || true

if [[ "$MIN_ROWS" =~ ^[0-9]+$ ]] && [[ "$MIN_ROWS" -gt 0 ]]; then
  bad="$("${PSQL[@]}" -tAc "
SELECT string_agg(tbl || '=' || n::text, ', ')
FROM (
  SELECT 'raw.kafka_orders' AS tbl, count(*)::bigint AS n FROM raw.kafka_orders
  UNION ALL SELECT 'raw.kafka_payments', count(*) FROM raw.kafka_payments
  UNION ALL SELECT 'raw.oltp_orders', count(*) FROM raw.oltp_orders
) s WHERE n < ${MIN_ROWS};
")"
  if [[ -n "${bad// /}" ]]; then
    echo "FAIL: tables below --min-rows ${MIN_ROWS}: ${bad}" >&2
    exit 1
  fi
  echo "OK all key raw tables have n >= ${MIN_ROWS}"
fi

echo "verify_raw_layer.sh finished OK."
