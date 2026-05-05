#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
SKIP_LOGS=0
SKIP_DB=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --skip-logs) SKIP_LOGS=1 ;;
    --skip-db) SKIP_DB=1 ;;
    -h|--help)
      echo "Usage: $0 [--dry-run] [--skip-logs] [--skip-db]"
      echo "  Stops Airflow scheduler/webserver/triggerer, removes airflow_logs volume (unless --skip-logs),"
      echo "  recreates Airflow DB on postgres_metadb (unless --skip-db), builds airflow_init, runs migrate+admin+connections,"
      echo "  recreates Airflow services. Does not touch OLAP, Spark volumes, or full pg_meta_data."
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

set -a
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck source=/dev/null
  . "$ROOT/.env"
fi
set +a

AIRFLOW_DB="${AIRFLOW_DB_NAME:-airflow}"
META_USER="${PG_META_USER:?PG_META_USER must be set (source .env)}"
META_PASS="${PG_META_PASSWORD:?PG_META_PASSWORD must be set}"
META_DB="${PG_META_DB:-metadb}"

echo "== [1/6] Stop Airflow services =="
run docker compose stop airflow_scheduler airflow_webserver airflow_triggerer 2>/dev/null || true
echo "Removing stopped Airflow containers (required before deleting airflow_logs volume)..."
run docker compose rm -f airflow_scheduler airflow_webserver airflow_triggerer airflow_init 2>/dev/null || true

if [[ "$SKIP_LOGS" -ne 1 ]]; then
  echo "== [2/6] Remove airflow_logs Docker volume =="
  log_vols=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && log_vols+=("$line")
  done < <(docker volume ls -q | grep -E '_airflow_logs$|^airflow_logs$' || true)
  if [[ ${#log_vols[@]} -eq 0 ]]; then
    echo "No airflow_logs volume found (ok if first run)."
  elif [[ ${#log_vols[@]} -gt 1 ]]; then
    echo "Multiple airflow_logs-like volumes; remove manually:" >&2
    printf '  %s\n' "${log_vols[@]}" >&2
    exit 1
  else
    echo "Removing volume: ${log_vols[0]}"
    run docker volume rm "${log_vols[0]}"
  fi
else
  echo "== [2/6] Skip logs volume (--skip-logs) =="
fi

if [[ "$SKIP_DB" -ne 1 ]]; then
  echo "== [3/6] Recreate Postgres database ${AIRFLOW_DB} on postgres_metadb =="
  run docker compose exec -T -e "PGPASSWORD=${META_PASS}" postgres_metadb \
    psql -U "${META_USER}" -d "${META_DB}" -v ON_ERROR_STOP=1 -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${AIRFLOW_DB}' AND pid <> pg_backend_pid();"
  run docker compose exec -T -e "PGPASSWORD=${META_PASS}" postgres_metadb \
    psql -U "${META_USER}" -d "${META_DB}" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${AIRFLOW_DB};"
  run docker compose exec -T -e "PGPASSWORD=${META_PASS}" postgres_metadb \
    psql -U "${META_USER}" -d "${META_DB}" -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${AIRFLOW_DB};"
else
  echo "== [3/6] Skip DB recreate (--skip-db) =="
fi

echo "== [4/6] docker compose build airflow_init =="
run docker compose build airflow_init

echo "== [5/6] airflow_init (db migrate, users, connections) =="
run docker compose run --rm airflow_init

echo "== [6/6] Recreate Airflow scheduler / webserver / triggerer =="
run docker compose up -d --force-recreate airflow_scheduler airflow_webserver airflow_triggerer

if docker compose ps --status running --quiet ingress 2>/dev/null | grep -q .; then
  echo "Reloading ingress (Airflow webserver IP may have changed)..."
  run docker compose exec -T ingress nginx -s reload
else
  echo "ingress not running; skip nginx reload."
fi

echo "airflow_dev_reset.sh finished OK."
