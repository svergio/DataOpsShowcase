# Infrastructure Tooling Layers

This directory stores additive tooling layers that extend `docker-compose.yml` without changing the core demo platform defaults.

## Compose overlays
- `vault/docker-compose.vault.yml` (`vault` profile)
- `lakefs/docker-compose.lakefs.yml` (`lakefs` profile)
- `datahub/docker-compose.datahub.yml` (`datahub` profile)
- `argocd/docker-compose.argocd.yml` (`argocd` profile)

## Compose strategy
- Core stack only: `docker compose -f docker-compose.yml up -d`
- Full stack: compose base + all overlays with profiles.
- Validation: `make tools-config` (full), `make tools-config-lite` (core only).

## Notes
- All overlays join existing `dataops_net`.
- Secrets are placeholders and must be replaced for shared environments.
