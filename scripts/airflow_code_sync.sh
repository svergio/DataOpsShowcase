#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "Usage: $0"
      echo "  Rebuild Airflow image from repo, run one-off airflow_init (migrate/admin/connections),"
      echo "  recreate scheduler/webserver/triggerer, reload ingress for /airflow/."
      echo "  Use after git pull or edits under pipelines/, services/, configs/airflow/."
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

docker compose build airflow_init
docker compose run --rm airflow_init
docker compose up -d --force-recreate airflow_scheduler airflow_webserver airflow_triggerer
"$ROOT/scripts/ingress_portal_reload.sh"
echo "airflow_code_sync.sh finished OK."
