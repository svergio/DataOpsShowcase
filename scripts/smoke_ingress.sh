#!/usr/bin/env bash
set -euo pipefail

BASE="${INGRESS_BASE_URL:-http://localhost:8090}"
BASE="${BASE%/}"

expect_url() {
  local name="$1"
  local url="$2"
  local out
  out=$(curl --connect-timeout 5 --max-time 30 -fsS -o /dev/null -w "%{http_code}" "$url") || true
  if [[ "${out:-}" =~ ^(200|302|301)$ ]]; then
    echo "OK:${out} ${name} ${url}"
  else
    echo "FAIL:http_status=${out:-} ${name} ${url}" >&2
    return 1
  fi
}

echo "Smoke ingress BASE=${BASE}"
expect_url root "${BASE}/"
expect_url dbt-web "${BASE}/dbt-web/"
expect_url dbt-api-health "${BASE}/dbt-api/v1/health"
expect_url airflow "${BASE}/airflow/"
expect_url mlflow "${BASE}/mlflow/"
expect_url grafana "${BASE}/grafana/"
echo "All ingress checks passed."
