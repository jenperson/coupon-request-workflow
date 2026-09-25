.PHONY: start-worker execute installdeps lint format typecheck lint-workflows check

## Install dependencies
installdeps:
	uv sync

## Check workflow code with ruff (lint + format check)
lint:
	uv run ruff check src/workflows/
	uv run ruff format --check src/workflows/

## Auto-format workflow code and apply ruff autofixes
format:
	uv run ruff format src/workflows/
	uv run ruff check --fix src/workflows/

## Type-check workflow code with mypy
typecheck:
	uv run mypy src/workflows/

## Lint workflows for determinism / I/O / structure issues (semgrep, advisory)
lint-workflows:
	uv run semgrep --config .agents/skills/workflows/scripts/linting/rules/ --quiet src/workflows/

## Run all checks: ruff lint, mypy types, and workflow lint
check: lint typecheck lint-workflows

## Auto-discover all workflows and start the worker (with file-watch auto-reload)
start-worker:
	uv run python -m entrypoints.dev

## Trigger a workflow execution
## Usage: make execute workflow=hello-world input='{"name": "World"}'
execute:
	uv run python -m entrypoints.start $(if $(workflow),--workflow $(workflow),) $(if $(input),--input '$(input)',)

