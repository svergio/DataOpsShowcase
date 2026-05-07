#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

LAKEFS_ENDPOINT="${LAKEFS_ENDPOINT:-http://127.0.0.1:${LAKEFS_PORT:-8008}}"
LAKECTL_IMAGE="${LAKECTL_IMAGE:-treeverse/lakectl:v1.36.0}"
ACCESS_KEY="${LAKEFS_ACCESS_KEY_ID:-lakefsadmin}"
SECRET_KEY="${LAKEFS_SECRET_ACCESS_KEY:-lakefsadmin}"
REPO_NAME="${LAKEFS_REPO_NAME:-dataops-showcase}"

echo "Waiting for lakeFS at ${LAKEFS_ENDPOINT}"
for _ in $(seq 1 30); do
  if curl -sf "${LAKEFS_ENDPOINT}/_health" >/dev/null; then
    break
  fi
  sleep 2
done

if ! curl -sf "${LAKEFS_ENDPOINT}/_health" >/dev/null; then
  echo "lakeFS is not healthy."
  exit 1
fi

echo "Ensuring lakeFS setup and repository exist."
docker run --rm \
  --network dataops_net \
  -e LAKECTL_SERVER_ENDPOINT="http://dataops_lakefs:8000" \
  -e LAKECTL_CREDENTIALS_ACCESS_KEY_ID="${ACCESS_KEY}" \
  -e LAKECTL_CREDENTIALS_SECRET_ACCESS_KEY="${SECRET_KEY}" \
  "${LAKECTL_IMAGE}" \
  lakectl repo create "lakefs://${REPO_NAME}" "s3://lakefs/${REPO_NAME}" --if-not-exists || true

docker run --rm \
  --network dataops_net \
  -e LAKECTL_SERVER_ENDPOINT="http://dataops_lakefs:8000" \
  -e LAKECTL_CREDENTIALS_ACCESS_KEY_ID="${ACCESS_KEY}" \
  -e LAKECTL_CREDENTIALS_SECRET_ACCESS_KEY="${SECRET_KEY}" \
  "${LAKECTL_IMAGE}" \
  lakectl branch create "lakefs://${REPO_NAME}" main --source "lakefs://${REPO_NAME}@main" >/dev/null 2>&1 || true

echo "lakeFS bootstrap complete for repo ${REPO_NAME}."
