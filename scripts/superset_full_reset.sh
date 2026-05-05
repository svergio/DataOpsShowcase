#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $0"
  echo "  Drops the Superset metadata database, re-runs superset_init (db upgrade, admin, init, bootstrap),"
  echo "  and starts superset. Requires docker compose and .env with PG_META_* and SUPERSET_DB_NAME."
  echo "  See docs/SUPERSET.md."
  exit 0
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source ./.env
  set +a
fi

DB="${SUPERSET_DB_NAME:-superset}"
USER="${PG_META_USER:-meta_user}"

echo "Stopping superset..."
docker compose stop superset 2>/dev/null || true

echo "Recreating Postgres database ${DB} on postgres_metadb..."
docker compose exec -T postgres_metadb psql -U "${USER}" -d postgres -v ON_ERROR_STOP=1 -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB}' AND pid <> pg_backend_pid();" \
  >/dev/null || true
docker compose exec -T postgres_metadb psql -U "${USER}" -d postgres -v ON_ERROR_STOP=1 -c \
  "DROP DATABASE IF EXISTS \"${DB}\" WITH (FORCE);"
docker compose exec -T postgres_metadb psql -U "${USER}" -d postgres -v ON_ERROR_STOP=1 -c \
  "CREATE DATABASE \"${DB}\" OWNER \"${USER}\";"

echo "Building and running superset_init..."
docker compose build superset_init
docker compose run --rm superset_init

echo "Starting superset..."
docker compose up -d superset

echo "superset_full_reset.sh finished OK."
