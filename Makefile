# SYSGrow Backend — Developer Task Runner
# Usage: make <target>
# Requires: activated .venv  (see README.md for setup)

.DEFAULT_GOAL := help
PYTHON       := python
PYTEST       := pytest
RUFF         := ruff
BANDIT       := bandit

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
	$(PYTEST) tests/ -x -q --tb=short --timeout=30

security:        ## Run Bandit security scan on app/
	$(BANDIT) -r app/ -c pyproject.toml -q

# ── Development ──────────────────────────────────────────────────────
.PHONY: run install clean

run:             ## Start development server (auto-reload)
	$(PYTHON) start_dev.py

install:         ## Install essential + dev dependencies
	pip install -r requirements-essential.txt
	pip install -r requirements-dev.txt

clean:           ## Remove caches, bytecode, and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage

# ── All-in-one ───────────────────────────────────────────────────────
.PHONY: ci

ci: check test security  ## Run full CI pipeline locally

# ── Help ─────────────────────────────────────────────────────────────
.PHONY: help

help:            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
