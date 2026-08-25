.PHONY: help install install-dev test lint format fmt typecheck check pre-commit clean clean-all coverage run-brief run-forecast db-migrate db-migrate-down db-reset update-deps

# Tool resolution (added 2026-08-24).
# Before this, every recipe called bare `pytest` / `ruff` / `mypy`, which only
# resolve inside an activated venv. Measured on 2026-08-24 in a plain shell:
# `make lint` exited 127 ("ruff: No such file or directory"). A gate that only
# works in one shell is not a gate, so resolution is explicit here:
#   1. an already-activated virtualenv ($VIRTUAL_ENV), then
#   2. this repo's own ./venv or ./.venv, then
#   3. whatever is on PATH (this is the CI path -- .github/workflows/ci.yml
#      pip-installs requirements-dev.txt and has no venv directory).
# NB: the $(if ...) guard matters -- an unset VIRTUAL_ENV would otherwise make
# the first candidate "/bin", which exists and would shadow the venv.
VENV_CANDIDATES := $(if $(VIRTUAL_ENV),$(VIRTUAL_ENV)/bin) venv/bin .venv/bin
VENV_BIN := $(firstword $(wildcard $(VENV_CANDIDATES)))
ifeq ($(VENV_BIN),)
PYTHON := python3
PYTEST := pytest
RUFF   := ruff
MYPY   := mypy
else
PYTHON := $(VENV_BIN)/python
PYTEST := $(VENV_BIN)/pytest
RUFF   := $(VENV_BIN)/ruff
MYPY   := $(VENV_BIN)/mypy
endif

help:
	@echo "InsightWeaver - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install         Install production dependencies"
	@echo "  make install-dev     Install development dependencies"
	@echo "  make update-deps     Update dependency lockfiles"
	@echo ""
	@echo "Development:"
	@echo "  make test            Run tests"
	@echo "  make coverage        Run tests with coverage report"
	@echo "  make lint            Run linter (ruff)"
	@echo "  make format          Auto-format code with ruff"
	@echo "  make fmt             Alias for 'make format'"
	@echo "  make typecheck       Run type checker (mypy)"
	@echo "  make pre-commit      Run all pre-commit hooks"
	@echo "  make check           Run all checks (lint + typecheck + test)"
	@echo ""
	@echo "Application:"
	@echo "  make run-brief       Run intelligence brief"
	@echo "  make run-forecast    Run forecast generation"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate      Run database migrations"
	@echo "  make db-migrate-down Rollback database migrations"
	@echo "  make db-reset        Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Remove build artifacts and cache"
	@echo "  make clean-all       Deep clean including venv"

install:
	pip install -r requirements.txt
	pip install -e .

install-dev:
	pip install -r requirements-dev.txt
	pip install -e .
	pre-commit install

update-deps:
	pip-compile pyproject.toml -o requirements.txt
	pip-compile --extra dev pyproject.toml -o requirements-dev.txt

test:
	$(PYTEST) tests/ -v

coverage:
	$(PYTEST) tests/ --cov=src --cov-report=term-missing -v

lint:
	$(RUFF) check src/ tests/

format:
	$(RUFF) format src/ tests/
	$(RUFF) check --fix src/ tests/

# fmt is the machine-facing name of `format`. The four verbs check/test/lint/fmt
# are identical across every repo in this workspace (added 2026-08-24).
fmt: format

typecheck:
	$(MYPY) src/ --show-error-codes --pretty

pre-commit:
	pre-commit run --all-files

check: lint typecheck test
	@echo "All checks passed."

run-brief:
	insightweaver brief

run-forecast:
	insightweaver forecast

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/

clean-all: clean
	rm -rf venv/
	rm -rf .venv/

db-migrate:
	python -m src.database.migrations.add_forecast_tables

db-migrate-down:
	python -m src.database.migrations.add_forecast_tables down

db-reset:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		rm -f data/insightweaver.db; \
		python -m src.database.migrations.add_forecast_tables; \
	else \
		echo "Cancelled"; \
	fi
