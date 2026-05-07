.PHONY: smoke smoke-ingress p0-verify dqc-help run-dqc up up-lite vault-init lakefs-setup datahub-ingest gitops-sync tools-config tools-config-lite

ROOT := $(CURDIR)
COMPOSE ?= docker compose
BASE_COMPOSE_FILES := -f docker-compose.yml
TOOLS_COMPOSE_FILES := \
	-f infrastructure/vault/docker-compose.vault.yml \
	-f infrastructure/lakefs/docker-compose.lakefs.yml \
	-f infrastructure/datahub/docker-compose.datahub.yml \
	-f infrastructure/argocd/docker-compose.argocd.yml

COMPOSE_BASE := $(COMPOSE) $(BASE_COMPOSE_FILES)
COMPOSE_ALL := $(COMPOSE) $(BASE_COMPOSE_FILES) $(TOOLS_COMPOSE_FILES)

smoke smoke-ingress:
	@chmod +x $(ROOT)/scripts/smoke_ingress.sh
	@$(ROOT)/scripts/smoke_ingress.sh

p0-verify:
	@chmod +x $(ROOT)/scripts/p0_verify.sh
	@$(ROOT)/scripts/p0_verify.sh

dqc-help:
	@echo "Tests and DQ: docs/TESTING_AND_DATA_QUALITY.md"
	@echo "Run DQC (needs dbt CLI + OLAP): make run-dqc"

run-dqc:
	@chmod +x $(ROOT)/scripts/run_dqc.sh
	@$(ROOT)/scripts/run_dqc.sh

tools-config:
	@$(COMPOSE_ALL) config >/dev/null
	@echo "Compose config OK (core + tools profiles)"

tools-config-lite:
	@$(COMPOSE_BASE) config >/dev/null
	@echo "Compose config OK (core stack only)"

up:
	@$(COMPOSE_ALL) --profile vault --profile lakefs --profile datahub --profile argocd up -d

up-lite:
	@$(COMPOSE_BASE) up -d

vault-init:
	@chmod +x $(ROOT)/infrastructure/vault/scripts/bootstrap-vault.sh
	@$(ROOT)/infrastructure/vault/scripts/bootstrap-vault.sh

lakefs-setup:
	@chmod +x $(ROOT)/infrastructure/lakefs/scripts/bootstrap-lakefs.sh
	@$(ROOT)/infrastructure/lakefs/scripts/bootstrap-lakefs.sh

datahub-ingest:
	@chmod +x $(ROOT)/infrastructure/datahub/scripts/run-ingestion.sh
	@$(ROOT)/infrastructure/datahub/scripts/run-ingestion.sh

gitops-sync:
	@chmod +x $(ROOT)/infrastructure/argocd/scripts/gitops-sync.sh
	@$(ROOT)/infrastructure/argocd/scripts/gitops-sync.sh
