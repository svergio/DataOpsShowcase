.PHONY: smoke smoke-ingress p0-verify dqc-help run-dqc

ROOT := $(CURDIR)

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
