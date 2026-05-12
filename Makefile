.PHONY: help install install-dev test lint format typecheck pre-commit clean clean-all coverage run-brief run-forecast db-migrate db-migrate-down db-reset update-deps

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
	pytest tests/ -v

coverage:
	pytest tests/ --cov=src --cov-report=term-missing -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy src/ --show-error-codes --pretty

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
