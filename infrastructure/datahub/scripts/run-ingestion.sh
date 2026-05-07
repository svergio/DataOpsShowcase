#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

RECIPE="${1:-infrastructure/datahub/ingestion/recipes/postgres_olap_to_datahub.yml}"

if [ ! -f "${RECIPE}" ]; then
  echo "Recipe not found: ${RECIPE}"
  echo "Available recipes:"
  ls infrastructure/datahub/ingestion/recipes
  exit 1
fi

echo "Running DataHub ingestion recipe: ${RECIPE}"
docker run --rm \
  --network dataops_net \
  -v "${ROOT_DIR}:/workspace" \
  acryldata/datahub-ingestion:v0.14.1 \
  datahub ingest -c "/workspace/${RECIPE}"

echo "Ingestion completed."
