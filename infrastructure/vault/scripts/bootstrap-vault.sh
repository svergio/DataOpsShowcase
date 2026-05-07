#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:${VAULT_PORT:-8200}}"
UNSEAL_KEYS_FILE="${ROOT_DIR}/infrastructure/vault/.vault-unseal-keys.json"
TOKEN_FILE="${ROOT_DIR}/infrastructure/vault/.vault-root-token"

echo "Checking Vault status at ${VAULT_ADDR}"
if ! docker compose -f infrastructure/vault/docker-compose.vault.yml --profile vault ps vault >/dev/null 2>&1; then
  echo "Vault container is not running. Start it first: make up"
  exit 1
fi

if docker exec dataops_vault sh -c "vault status -format=json" >/tmp/vault_status.json 2>/dev/null; then
  if rg -q '"initialized":true' /tmp/vault_status.json; then
    echo "Vault already initialized."
  else
    echo "Initializing Vault..."
    docker exec dataops_vault sh -c "vault operator init -format=json" | tee "${UNSEAL_KEYS_FILE}" >/dev/null
    rg '"root_token"' "${UNSEAL_KEYS_FILE}" | sed -E 's/.*"root_token":"([^"]+)".*/\1/' > "${TOKEN_FILE}"

    echo "Unsealing Vault..."
    for idx in 0 1 2; do
      key="$(python3 -c "import json; print(json.load(open('${UNSEAL_KEYS_FILE}'))['unseal_keys_b64'][${idx}])")"
      docker exec dataops_vault sh -c "vault operator unseal ${key}" >/dev/null
    done
  fi
else
  echo "Vault CLI status call failed."
  exit 1
fi

if [ ! -f "${TOKEN_FILE}" ]; then
  echo "Root token file not found: ${TOKEN_FILE}"
  exit 1
fi

VAULT_TOKEN="$(cat "${TOKEN_FILE}")"
echo "Configuring KV and policy..."
docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" dataops_vault sh -c "vault secrets enable -path=kv kv-v2 >/dev/null 2>&1 || true"
docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" dataops_vault sh -c "vault policy write dataops-read /vault/policies/dataops-read.hcl"
docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" dataops_vault sh -c "vault kv put kv/dataops/bootstrap placeholder=change-me"

echo "Vault bootstrap complete."
echo "Root token stored in infrastructure/vault/.vault-root-token (local dev only)."
