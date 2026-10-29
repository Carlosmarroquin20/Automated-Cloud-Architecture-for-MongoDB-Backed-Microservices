# Developer task shortcuts. Targets mirror the CI quality gates so local runs and
# the pipeline enforce the same checks. Requires GNU make.

.DEFAULT_GOAL := help
.PHONY: help install lint typecheck test contract openapi check up down observability-up validate

BACKEND := src/backend
AUDIT := src/audit
FRONTEND := src/frontend

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-18s %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd $(BACKEND) && pip install -r requirements-dev.txt
	cd $(AUDIT) && pip install -r requirements-dev.txt
	cd $(FRONTEND) && npm ci

lint: ## Lint the Python services (ruff) and frontend (eslint)
	cd $(BACKEND) && ruff check .
	cd $(AUDIT) && ruff check .
	cd $(FRONTEND) && npm run lint

typecheck: ## Type-check the Python services (mypy) and frontend (tsc)
	cd $(BACKEND) && mypy app tests scripts
	cd $(AUDIT) && mypy app tests
	cd $(FRONTEND) && npm run typecheck

test: ## Run the Python service (pytest) and frontend (vitest) suites
	cd $(BACKEND) && pytest -q
	cd $(AUDIT) && pytest -q
	cd $(FRONTEND) && npm test

contract: ## Fail if the OpenAPI or AsyncAPI contract no longer matches the code
	cd $(BACKEND) && python scripts/export_openapi.py --check
	cd $(BACKEND) && pytest -q tests/test_asyncapi_contract.py

openapi: ## Regenerate the committed OpenAPI contract (docs/api/openapi.json)
	cd $(BACKEND) && python scripts/export_openapi.py

check: lint typecheck test contract ## Run every quality gate

up: ## Start the full stack (docker compose)
	docker compose up --build

down: ## Stop the stack and remove volumes
	docker compose down -v

observability-up: ## Start the stack with Prometheus and Grafana
	docker compose --profile observability up --build

validate: ## Validate Terraform and Kubernetes manifests
	terraform -chdir=terraform fmt -check -recursive
	terraform -chdir=terraform init -backend=false -input=false >/dev/null
	terraform -chdir=terraform validate -no-color
	kubectl kustomize k8s/base >/dev/null
	kubectl kustomize k8s/overlays/dev >/dev/null
	kubectl kustomize k8s/monitoring >/dev/null
