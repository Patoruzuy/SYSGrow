# SYSGrow Backend — Developer Task Runner
# Usage: make <target>
# Requires: activated .venv  (see README.md for setup)

.DEFAULT_GOAL := help
PYTHON       ?= python3.11
VENV_DIR     ?= .venv
PYTEST_ARGS  ?= -x -q --tb=short
ifeq ($(wildcard $(VENV_DIR)/Scripts/python.exe),$(VENV_DIR)/Scripts/python.exe)
VENV_PYTHON  := $(VENV_DIR)/Scripts/python.exe
else
VENV_PYTHON  := $(VENV_DIR)/bin/python
endif
PYTEST       := $(VENV_PYTHON) -m pytest
RUFF         := $(VENV_PYTHON) -m ruff
BANDIT       := $(VENV_PYTHON) -m bandit
BANDIT_REPORT ?= bandit_report.json
COMPOSE      ?= docker compose
DOCKER_SERVICE ?= sysgrow
OPS_ENV      ?= ops.env
HEALTH_TIMEOUT ?= 120
HEALTH_INTERVAL ?= 5

# ── Quality ──────────────────────────────────────────────────────────
.PHONY: lint format check test security

lint:            ## Run linter (Ruff check)
	$(RUFF) check .

format:          ## Auto-format code (Ruff format)
	$(RUFF) format .

check:           ## Lint + format check (no writes)
	$(RUFF) check .
	$(RUFF) format --check .

test:            ## Run test suite
	$(PYTEST) tests/ $(PYTEST_ARGS)

security:        ## Run Bandit security scan on app/
	$(BANDIT) -r app/ -c pyproject.toml -f json -o $(BANDIT_REPORT)

# ── Development ──────────────────────────────────────────────────────
.PHONY: run install clean

run:             ## Start development server (auto-reload)
	$(PYTHON) start_dev.py

install:         ## Install essential + dev dependencies
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements-essential.txt
	$(VENV_PYTHON) -m pip install -r requirements-dev.txt

clean:           ## Remove caches, bytecode, and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage

# ── Docker ───────────────────────────────────────────────────────────
.PHONY: docker-check docker-build docker-up docker-down docker-logs docker-ps docker-health deploy-safe

docker-check:    ## Validate Docker and required env file for compose deployment
	@docker --version >/dev/null
	@$(COMPOSE) version >/dev/null
	@test -f $(OPS_ENV) || (echo "Missing $(OPS_ENV). Copy ops.env.example to $(OPS_ENV) and configure it."; exit 1)

docker-build:    ## Build Docker images
	$(COMPOSE) build --pull

docker-up:       ## Start Docker services
	$(COMPOSE) up -d --remove-orphans

docker-down:     ## Stop Docker services
	$(COMPOSE) down

docker-logs:     ## Follow backend service logs
	$(COMPOSE) logs -f $(DOCKER_SERVICE)

docker-ps:       ## Show compose service status
	$(COMPOSE) ps

docker-health:   ## Wait for backend container health check to pass
	@cid="$$( $(COMPOSE) ps -q $(DOCKER_SERVICE) )"; \
	if [ -z "$$cid" ]; then echo "Service $(DOCKER_SERVICE) is not running"; exit 1; fi; \
	elapsed=0; \
	while [ $$elapsed -lt $(HEALTH_TIMEOUT) ]; do \
		status="$$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' $$cid 2>/dev/null || echo unknown)"; \
		if [ "$$status" = "healthy" ] || [ "$$status" = "running" ]; then \
			echo "Service $(DOCKER_SERVICE) is $$status"; \
			exit 0; \
		fi; \
		if [ "$$status" = "unhealthy" ] || [ "$$status" = "exited" ] || [ "$$status" = "dead" ]; then \
			echo "Service $(DOCKER_SERVICE) failed health check with status=$$status"; \
			$(COMPOSE) logs --tail=150 $(DOCKER_SERVICE); \
			exit 1; \
		fi; \
		sleep $(HEALTH_INTERVAL); \
		elapsed=$$((elapsed + $(HEALTH_INTERVAL))); \
	done; \
	echo "Timed out waiting for $(DOCKER_SERVICE) health after $(HEALTH_TIMEOUT)s"; \
	$(COMPOSE) logs --tail=150 $(DOCKER_SERVICE); \
	exit 1

deploy-safe: check security test docker-check docker-build docker-up docker-health ## Run quality gates, deploy with Docker, and verify health

# ── All-in-one ───────────────────────────────────────────────────────
.PHONY: ci

ci: check test security  ## Run full CI pipeline locally

# ── Help ─────────────────────────────────────────────────────────────
.PHONY: help

help:            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
