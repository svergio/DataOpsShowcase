.PHONY: smoke smoke-ingress p0-verify dqc-help

ROOT := $(CURDIR)

smoke smoke-ingress:
	@chmod +x $(ROOT)/scripts/smoke_ingress.sh
	@$(ROOT)/scripts/smoke_ingress.sh

p0-verify:
	@chmod +x $(ROOT)/scripts/p0_verify.sh
	@$(ROOT)/scripts/p0_verify.sh

dqc-help:
	@echo "Independent DQC: see monitoring/quality/README.md"
