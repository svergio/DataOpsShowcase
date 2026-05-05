#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MIN_ROWS=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --min-rows)
      MIN_ROWS="${2:?}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--min-rows N]"
      echo "  Print row counts for staging.stg_* filled by Spark preprocess; default --min-rows 1."
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

echo "=== staging row counts ==="
"${PSQL[@]}" -c "
SELECT 'staging.stg_orders' AS tbl, count(*)::bigint AS n FROM staging.stg_orders
UNION ALL SELECT 'staging.stg_customers', count(*) FROM staging.stg_customers
UNION ALL SELECT 'staging.stg_order_events', count(*) FROM staging.stg_order_events
UNION ALL SELECT 'staging.stg_payment_events', count(*) FROM staging.stg_payment_events
ORDER BY 1;
"

bad="$("${PSQL[@]}" -tAc "
SELECT string_agg(tbl || '=' || n::text, ', ')
FROM (
  SELECT 'staging.stg_orders' AS tbl, count(*)::bigint AS n FROM staging.stg_orders
  UNION ALL SELECT 'staging.stg_customers', count(*) FROM staging.stg_customers
  UNION ALL SELECT 'staging.stg_order_events', count(*) FROM staging.stg_order_events
  UNION ALL SELECT 'staging.stg_payment_events', count(*) FROM staging.stg_payment_events
) s WHERE n < ${MIN_ROWS};
")"
if [[ -n "${bad// /}" ]]; then
  echo "FAIL: tables below --min-rows ${MIN_ROWS}: ${bad}" >&2
  exit 1
fi

echo "OK staging tables have n >= ${MIN_ROWS}"
echo "verify_staging_post_spark.sh finished OK."
