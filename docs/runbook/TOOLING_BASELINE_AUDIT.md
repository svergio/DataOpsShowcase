# Tooling Baseline Audit

## Baseline checked
- Existing compose topology (`docker-compose.yml`) with ingress-centric access model.
- Current docs map (`README.md`, `docs/README.md`) and runbook coverage.
- Integration anchors: `dataops_net`, `postgres_metadb`, `kafka`, `schema_registry`, `minio`, ingress routes.

## Findings
- Core stack is healthy as a single compose file and should remain default.
- `infrastructure/` was empty, so tooling phases can be additive with profile-gated compose files.
- Existing `Makefile` had only smoke and DQ helpers; no tooling lifecycle targets.
- Runbooks for Vault/lakeFS/DataHub/ArgoCD were missing.

## Integration decisions
- Keep core stack untouched, add tooling as optional compose overlays.
- Reuse `dataops_net` to avoid cross-stack DNS/network drift.
- Use profile isolation: `vault`, `lakefs`, `datahub`, `argocd`.
- Keep placeholders for secrets; no real credentials in repo.
