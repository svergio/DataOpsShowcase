#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${INGRESS_PORT:-8090}"
BASE="${INGRESS_BASE_URL:-http://localhost:${PORT}}"

curl_fail() {
  local url="$1"
  local label="$2"
  if ! curl -sfS --max-time 15 -o /dev/null "$url"; then
    echo "FAIL: $label -> $url" >&2
    return 1
  fi
  echo "OK: $label"
}

cd "$ROOT"
curl_fail "${BASE}/" "portal root"
curl_fail "${BASE}/superset/health" "superset health (via ingress)"
curl_fail "${BASE}/nl2sql/health" "nl2sql health (via ingress)"
curl_fail "${BASE}/prometheus/-/healthy" "prometheus (via ingress)"
echo "ingress_smoke: all checks passed (BASE=$BASE)"
