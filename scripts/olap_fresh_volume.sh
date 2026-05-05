#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
SKIP_DOWN=0
YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --skip-down) SKIP_DOWN=1 ;;
    --yes) YES=1 ;;
    -h|--help)
      echo "Usage: $0 [--dry-run] [--skip-down] [--yes]"
      echo "  Stops compose (unless --skip-down), removes *pg_olap_data volume, docker compose up -d,"
      echo "  waits for postgres_olap healthy, runs dbt debug in dbt service."
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

VOLS=()
while IFS= read -r line; do
  [[ -n "$line" ]] && VOLS+=("$line")
done < <(docker volume ls -q | grep 'pg_olap_data' || true)

if [[ ${#VOLS[@]} -eq 0 ]]; then
  echo "No docker volume matching pg_olap_data found." >&2
  exit 1
fi

if [[ ${#VOLS[@]} -gt 1 ]]; then
  echo "Multiple volumes match pg_olap_data; remove manually:" >&2
  printf '  %s\n' "${VOLS[@]}" >&2
  exit 1
fi

VOL="${VOLS[0]}"
echo "Using volume: $VOL"

if [[ "$YES" -ne 1 && "$DRY_RUN" -ne 1 ]]; then
  read -r -p "Remove volume ${VOL} and recreate OLAP? [y/N] " ans
  case "$ans" in
    y|Y) ;;
    *) echo "Aborted." >&2; exit 1 ;;
  esac
fi

if [[ "$SKIP_DOWN" -ne 1 ]]; then
  run docker compose down
else
  echo "Skipping docker compose down (--skip-down)"
fi

run docker volume rm "$VOL"

run docker compose up -d

if [[ "$DRY_RUN" -eq 1 ]]; then
  exit 0
fi

echo "Waiting for postgres_olap to become healthy..."
for _ in $(seq 1 90); do
  st=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' postgres_olap 2>/dev/null || echo unknown)
  if [[ "$st" == "healthy" ]]; then
    echo "postgres_olap is healthy."
    break
  fi
  sleep 2
done

st=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' postgres_olap 2>/dev/null || echo unknown)
if [[ "$st" != "healthy" ]]; then
  echo "postgres_olap did not become healthy in time (last=$st)." >&2
  exit 1
fi

echo "Waiting for dbt image to finish pip install (if needed)..."
for _ in $(seq 1 60); do
  if docker exec dbt python -c "import dbt.version" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

DBT_VER="${DBT_IMAGE_TAG:-1.8.2}"
docker compose exec -T \
  -e "DBT_HOST=${DBT_HOST:-postgres_olap}" \
  -e "DBT_USER=${DBT_USER:-${PG_OLAP_USER:-olap_user}}" \
  -e "DBT_PASSWORD=${DBT_PASSWORD:-${PG_OLAP_PASSWORD:-olap_pass}}" \
  -e "DBT_DBNAME=${DBT_DBNAME:-${PG_OLAP_DB:-techmart_dwh}}" \
  dbt bash -lc "
    set -euo pipefail
    pip install -q --disable-pip-version-check 'dbt-postgres==${DBT_VER}'
    cd /workspace/dbt
    dbt debug --profiles-dir /workspace/dbt --project-dir /workspace/dbt
  "

echo "olap_fresh_volume.sh finished OK."
