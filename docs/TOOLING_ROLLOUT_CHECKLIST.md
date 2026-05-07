# Tooling Rollout Checklist

## Phase checklist
- [x] Baseline audit documented (`docs/runbook/TOOLING_BASELINE_AUDIT.md`)
- [x] Vault scaffolding added (`infrastructure/vault`)
- [x] lakeFS scaffolding added (`infrastructure/lakefs`)
- [x] DataHub migration artifacts and recipes added (`infrastructure/datahub`)
- [x] ArgoCD manifests and sync helper added (`infrastructure/argocd`)
- [x] Make targets for tooling lifecycle added
- [x] Runbooks and docs index updated

## Validation checklist
- [ ] `make tools-config`
- [ ] `make tools-config-lite`
- [ ] `make up-lite`
- [ ] `make up` (profiles enabled as needed)
- [ ] `make vault-init`
- [ ] `make lakefs-setup`
- [ ] `make datahub-ingest`
- [ ] `make gitops-sync`
