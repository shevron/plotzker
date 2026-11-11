# Common development commands. Setup details: README §10.

.DEFAULT_GOAL := help
.PHONY: help develop clean check typecheck format lint test stl render

PYTHON_VERSION := $(shell cat .python-version)
UV_RUN := uv run --extra dev

help:  ## List the available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

develop:  ## Set up the development environment (.venv on pyenv's Python, all dependencies)
	pyenv install --skip-existing $(PYTHON_VERSION)
	test -d .venv || uv venv --python "$$(pyenv which python)"
	uv sync --extra dev

clean:  ## Remove all generated files (STLs, renders, caches, build output); keeps .venv
	rm -rf stl renders build dist .pytest_cache .ruff_cache .mypy_cache
	find . -path ./.venv -prune -o -name __pycache__ -type d -exec rm -rf {} +

check: typecheck  ## Run the static code checks (ruff lint + formatting, mypy)
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .

typecheck:  ## Run the type checks (mypy)
	$(UV_RUN) mypy

format:  ## Re-format the code (ruff format)
	$(UV_RUN) ruff format .

lint:  ## Run ruff linting and apply its automatic fixes
	$(UV_RUN) ruff check --fix .

test:  ## Run the unit tests (pytest)
	$(UV_RUN) python -m pytest

stl:  ## Generate the STLs of all printable parts into stl/
	$(UV_RUN) python -m plotter_cad stl

render:  ## Generate PNG renders of all parts and assemblies into renders/ (needs the PythonSCAD app)
	$(UV_RUN) python -m plotter_cad render
