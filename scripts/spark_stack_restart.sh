#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAX_WAIT_SEC="${SPARK_HEALTH_MAX_WAIT:-120}"
WAIT_ITER=$((MAX_WAIT_SEC / 2))
if [[ "$WAIT_ITER" -lt 1 ]]; then WAIT_ITER=1; fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "Usage: $0"
      echo "  Restarts spark_master and spark_worker, then waits until both report healthy (docker healthcheck)."
      echo "  Env: SPARK_HEALTH_MAX_WAIT seconds (default 120). Poll every 2s."
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

echo "Restarting Spark master and worker..."
docker compose restart spark_master spark_worker

echo "Waiting for spark_master health (max ${MAX_WAIT_SEC}s)..."
ok=0
for _ in $(seq 1 "$WAIT_ITER"); do
  st=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' spark_master 2>/dev/null || echo unknown)
  if [[ "$st" == "healthy" ]]; then
    echo "spark_master is healthy."
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" -ne 1 ]]; then
  st=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' spark_master 2>/dev/null || echo unknown)
  echo "spark_master did not become healthy (last=$st)." >&2
  exit 1
fi

echo "Waiting for spark_worker health (max ${MAX_WAIT_SEC}s)..."
ok=0
for _ in $(seq 1 "$WAIT_ITER"); do
  st=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' spark_worker 2>/dev/null || echo unknown)
  if [[ "$st" == "healthy" ]]; then
    echo "spark_worker is healthy."
    echo "spark_stack_restart.sh finished OK."
    exit 0
  fi
  sleep 2
done

echo "spark_worker did not become healthy in time." >&2
exit 1
