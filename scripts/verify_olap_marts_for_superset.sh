#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker compose ps --status running --quiet postgres_olap 2>/dev/null | grep -q .; then
  echo "postgres_olap is not running. Start stack: docker compose up -d postgres_olap" >&2
  exit 1
fi

SQL="SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'dwh_marts'
  AND table_name IN (
    'fct_daily_sales','fct_orders','fct_payments',
    'dim_customers','dim_products',
    'redis_serving_snapshot'
  )
ORDER BY 1,2;"

docker compose exec -T postgres_olap psql -U "${PG_OLAP_USER:-olap_user}" -d "${PG_OLAP_DB:-techmart_dwh}" -v ON_ERROR_STOP=1 -c "$SQL"
