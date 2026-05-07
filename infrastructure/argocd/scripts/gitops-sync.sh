#!/usr/bin/env bash
set -euo pipefail

ARGOCD_SERVER="${ARGOCD_SERVER:-127.0.0.1:${ARGOCD_PORT:-8088}}"
ARGOCD_USER="${ARGOCD_USER:-admin}"
ARGOCD_PASSWORD="${ARGOCD_PASSWORD:-change-me}"
APP_NAME="${1:-dataops-dev}"

if ! command -v argocd >/dev/null 2>&1; then
  echo "argocd CLI is required. Install: https://argo-cd.readthedocs.io/en/stable/cli_installation/"
  exit 1
fi

echo "Logging into ArgoCD at ${ARGOCD_SERVER}"
argocd login "${ARGOCD_SERVER}" --username "${ARGOCD_USER}" --password "${ARGOCD_PASSWORD}" --insecure --grpc-web

echo "Syncing app ${APP_NAME}"
argocd app sync "${APP_NAME}" --grpc-web
argocd app wait "${APP_NAME}" --health --sync --timeout 300 --grpc-web

echo "ArgoCD sync complete for ${APP_NAME}"
