#!/usr/bin/env bash
set -euo pipefail

BASE="${INGRESS_BASE_URL:-http://localhost:8090}"
BASE="${BASE%/}"

expect_url() {
  local name="$1"
  local url="$2"
  local out
  out=$(curl --connect-timeout 5 --max-time 30 -fsS -o /dev/null -w "%{http_code}" "$url") || true
  if [[ "${out:-}" =~ ^(200|301|302|303|307|308)$ ]]; then
    echo "OK:${out} ${name} ${url}"
  else
    echo "FAIL:http_status=${out:-} ${name} ${url}" >&2
    return 1
  fi
}

expect_url_status() {
  local name="$1"
  local url="$2"
  local allowed_regex="$3"
  local out
  out=$(curl --connect-timeout 5 --max-time 30 -fsS -o /dev/null -w "%{http_code}" "$url") || true
  if [[ "${out:-}" =~ ${allowed_regex} ]]; then
    echo "OK:${out} ${name} ${url}"
  else
    echo "FAIL:http_status=${out:-} ${name} ${url}" >&2
    return 1
  fi
}

expect_response_contains() {
  local name="$1"
  local url="$2"
  local needle="$3"
  local body body_lc needle_lc
  body="$(curl --connect-timeout 5 --max-time 30 -fsSL "$url" || true)"
  body_lc=$(printf '%s' "$body" | tr '[:upper:]' '[:lower:]')
  needle_lc=$(printf '%s' "$needle" | tr '[:upper:]' '[:lower:]')
  if [[ "${body_lc}" == *"${needle_lc}"* ]]; then
    echo "OK:${name} body_contains=${needle}"
  else
    echo "FAIL:no_substring '${needle}' ${name} ${url}" >&2
    return 1
  fi
}

echo "Smoke ingress BASE=${BASE}"
expect_url root "${BASE}/"
expect_url dbt-ui "${BASE}/dbt/"
expect_url dbt-api-health "${BASE}/dbt-api/v1/health"
expect_url airflow "${BASE}/airflow/"
expect_url mlflow "${BASE}/mlflow/"
expect_url grafana "${BASE}/grafana/"
expect_url superset "${BASE}/superset/"
expect_url jupyter "${BASE}/jupyter/"
expect_response_contains prometheus_markup "${BASE}/prometheus/graph" "Prometheus"
expect_url pushgateway "${BASE}/pushgateway/"
expect_url spark-master "${BASE}/spark-master/"
expect_url spark-worker "${BASE}/spark-worker/"
expect_url minio-console "${BASE}/minio-console/"
expect_url_status atlas "${BASE}/atlas/" "^(200|301|302|303|307|308|401)$"
ALT_BASE="${INGRESS_ALT_BASE_URL:-}"
if [[ -n "${ALT_BASE}" ]]; then
  ALT_BASE="${ALT_BASE%/}"
  expect_url_status atlas_port80 "${ALT_BASE}/atlas/" "^(200|301|302|303|307|308|401)$"
fi
echo "All ingress checks passed."
