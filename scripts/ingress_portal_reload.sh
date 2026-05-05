#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NO_SMOKE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-smoke) NO_SMOKE=1 ;;
    -h|--help)
      echo "Usage: $0 [--no-smoke]"
      echo "  nginx -t (warn-only), build portal_web, recreate portal_web + ingress with --no-deps, optionally smoke_ingress.sh"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

set -a
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck source=/dev/null
  . "$ROOT/.env"
fi
set +a

echo "Validating nginx config (non-fatal before recreate)..."
if docker inspect dataops_ingress >/dev/null 2>&1; then
  if ! docker exec dataops_ingress nginx -t 2>&1; then
    echo "WARN: nginx -t failed on current ingress (upstream DNS may be incomplete)." >&2
  fi
else
  echo "WARN: dataops_ingress not running — skip nginx -t." >&2
fi

echo "Building portal_web (catalog.json baked into image)..."
docker compose build portal_web

echo "Recreating portal_web and ingress (--no-deps so Kafka/DB chain is not restarted)..."
docker compose up -d --no-deps --force-recreate portal_web
docker compose up -d --no-deps --force-recreate ingress

echo "nginx -t on new ingress..."
docker exec dataops_ingress nginx -t

if [[ "$NO_SMOKE" -eq 1 ]]; then
  echo "Skipping smoke_ingress (--no-smoke)."
  exit 0
fi

export INGRESS_BASE_URL="${INGRESS_BASE_URL:-http://localhost:${INGRESS_PORT:-8090}}"
chmod +x "$ROOT/scripts/smoke_ingress.sh"
exec "$ROOT/scripts/smoke_ingress.sh"
