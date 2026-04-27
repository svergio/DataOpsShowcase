SHELL := /bin/bash

BACKEND_DIR := backend
FRONTEND_DIR := frontend
OPENAPI_FILE := openapi/dbt_web.openapi.yaml

.PHONY: dbt-web-build dbt-web-run dbt-web-test dbt-web-openapi dbt-web-docs-refresh

dbt-web-build:
	docker build -f docker/Dockerfile.backend -t dataops/dbt-web-backend:local .
	docker build -f docker/Dockerfile.frontend -t dataops/dbt-web-frontend:local .

dbt-web-run:
	docker compose -f docker/docker-compose.fragment.yml up -d dbt-web-backend dbt-web-frontend

dbt-web-test:
	cd $(BACKEND_DIR) && python3 -m pytest -q

dbt-web-openapi:
	@echo "OpenAPI file: $(OPENAPI_FILE)"
	test -f "$(OPENAPI_FILE)"

dbt-web-docs-refresh:
	curl -fsS -X POST "http://localhost:8010/api/v1/docs/refresh" -H "Content-Type: application/json" -d '{"source":"manual"}'
