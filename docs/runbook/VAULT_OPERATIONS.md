# Vault Operations Runbook

## Scope
Runbook for local/dev Vault in `DataOpsShowcase` (`infrastructure/vault`).

## Start
```bash
make up
```

## Initialize and seed policy
```bash
make vault-init
```

## What bootstrap does
- Initializes and unseals Vault (if not initialized yet).
- Enables KV v2 at `kv/`.
- Applies policy `dataops-read`.
- Writes placeholder secret at `kv/dataops/bootstrap`.

## Common operations
```bash
# Read a secret
VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$(cat infrastructure/vault/.vault-root-token)" \
  vault kv get kv/dataops/bootstrap

# Put/update secret
VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$(cat infrastructure/vault/.vault-root-token)" \
  vault kv put kv/dataops/app db_password="replace-me"
```

## Security notes
- This setup is for local development only (file storage, no TLS).
- Never commit `.vault-root-token` and `.vault-unseal-keys.json`.
- Replace placeholder values before any shared environment usage.
