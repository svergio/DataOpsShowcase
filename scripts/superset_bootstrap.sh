#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "Usage: $0"
      echo "  Requires running superset service. Runs superset_bootstrap.py (datasets, dashboards)."
      echo "  See docs/SUPERSET.md."
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

if ! docker compose ps --status running --quiet superset 2>/dev/null | grep -q .; then
  echo "superset is not running. Start: docker compose up -d superset" >&2
  exit 1
fi

echo "Running superset_bootstrap.py..."
docker compose exec -T superset python /app/pythonpath/superset_bootstrap.py

echo "superset_bootstrap.sh finished OK."
