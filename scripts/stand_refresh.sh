#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

DO_OLAP=0
DO_INGRESS=0
DO_GENERATORS=0
DO_AIRFLOW=0
AIRFLOW_ARGS=()

usage() {
  echo "Usage: $0 [--olap-only] [--ingress-only] [--generators] [--airflow-sequence [args...]]"
  echo "  Combine flags as needed. At least one flag is required."
  echo "  Use --airflow-sequence last; all following args go to airflow_run_dags_sequence.py."
  exit "$1"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --olap-only) DO_OLAP=1 ;;
    --ingress-only) DO_INGRESS=1 ;;
    --generators) DO_GENERATORS=1 ;;
    --airflow-sequence)
      DO_AIRFLOW=1
      shift
      while [[ $# -gt 0 ]]; do
        AIRFLOW_ARGS+=("$1")
        shift
      done
      break
      ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown arg: $1" >&2; usage 1 ;;
  esac
  shift
done

if [[ "$DO_OLAP$DO_INGRESS$DO_GENERATORS$DO_AIRFLOW" == *"1"* ]]; then
  :
else
  echo "Select at least one of: --olap-only --ingress-only --generators --airflow-sequence" >&2
  usage 1
fi

if [[ "$DO_OLAP" -eq 1 ]]; then
  "$ROOT/scripts/olap_fresh_volume.sh" --yes
fi

if [[ "$DO_INGRESS" -eq 1 ]]; then
  "$ROOT/scripts/ingress_portal_reload.sh"
fi

if [[ "$DO_GENERATORS" -eq 1 ]]; then
  "$ROOT/scripts/generators_wait_ready.sh"
fi

if [[ "$DO_AIRFLOW" -eq 1 ]]; then
  docker exec airflow_webserver python /opt/airflow/pipelines/tools/airflow_run_dags_sequence.py "${AIRFLOW_ARGS[@]:-}"
fi

echo "stand_refresh.sh finished."
