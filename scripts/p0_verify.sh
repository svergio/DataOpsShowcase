#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== 1. Ingress URLs ==="
export INGRESS_BASE_URL="${INGRESS_BASE_URL:-http://localhost:8090}"
chmod +x "$ROOT/scripts/smoke_ingress.sh"
"$ROOT/scripts/smoke_ingress.sh"

echo ""
echo "=== 2. dbt (inside compose: dbt service) ==="
if docker compose ps --status running --format '{{.Name}}' 2>/dev/null | grep -qx 'dbt'; then
  docker compose exec -T dbt bash -c '
    set -e
    cd /workspace/dbt
    pip install -q --disable-pip-version-check dbt-postgres=='"${DBT_IMAGE_TAG:-1.8.2}"'
    export DBT_HOST=postgres_olap DBT_USER=olap_user DBT_PASSWORD=olap_pass DBT_DBNAME='"${PG_OLAP_DB:-techmart_dwh}"'
    dbt debug --profiles-dir . --project-dir .
    dbt source freshness --profiles-dir . --project-dir .
    dbt test --selector dqc_all_tests --profiles-dir . --project-dir .
  ' && echo "OK dbt freshness + test" || echo "FAIL dbt (see logs)" >&2
else
  echo "SKIP dbt: service not running (docker compose up -d dbt postgres_olap ...)"
fi

echo ""
echo "=== 3. meta views (postgres_olap) ==="
if docker compose ps --status running --format '{{.Name}}' 2>/dev/null | grep -qx 'postgres_olap'; then
  docker compose exec -T postgres_olap psql -U "${PG_OLAP_USER:-olap_user}" -d "${PG_OLAP_DB:-techmart_dwh}" -tc "SELECT count(*) FROM meta.v_pipeline_runs_recent;" && echo "OK meta.v_pipeline_runs_recent"
else
  echo "SKIP postgres_olap"
fi

echo ""
echo "=== 4. Grafana health ==="
G="${INGRESS_BASE_URL:-http://localhost:8090}"
G="${G%/}"
if curl -fsS --connect-timeout 3 "$G/grafana/api/health" >/dev/null 2>&1; then
  echo "OK Grafana /api/health"
else
  echo "Note: Could not reach Grafana API (auth or stack down)."
fi

echo "p0-verify finished."
