# Common development commands. Setup details: README §6.

.DEFAULT_GOAL := help
.PHONY: help develop clean check typecheck format lint test stl render render-inspect freecad fem fem-status diff

PYTHON_VERSION := $(shell cat .python-version)
UV_RUN := uv run --extra dev --extra diff

help:  ## List the available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

develop:  ## Set up the development environment (.venv on pyenv's Python, all dependencies)
	pyenv install --skip-existing $(PYTHON_VERSION)
	test -d .venv || uv venv --python "$$(pyenv which python)"
	uv sync --extra dev --extra diff

clean:  ## Remove all generated files (STLs, renders, FreeCAD assembly, caches, build output); keeps .venv
	rm -rf stl renders fem/results freecad/stl freecad/components.json freecad/*.FCStd freecad/*.FCBak build dist .pytest_cache .ruff_cache .mypy_cache
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

render-inspect:  ## Render every view (iso, rear iso, front, rear, left, right, top) into renders/inspect/; NAMES="x_carriage gantry" limits it
	$(UV_RUN) python -m plotter_cad render --inspect $(NAMES)

FREECAD_BIN ?= /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd

freecad:  ## Build the FreeCAD Assembly (freecad/PenPlotter.FCStd; needs FreeCAD 1.x, see freecad/README.md)
	$(UV_RUN) python -m plotter_cad freecad
	$(FREECAD_BIN) freecad/build_assembly.py

fem:  ## FEM check of parts into fem/results/ (needs FreeCAD's gmsh and CalculiX); NAMES="x_idler_slider ..."
	$(UV_RUN) python -m plotter_cad fem $(NAMES)

fem-status:  ## FEM state of every printable part; flags verdicts that are stale (spec or geometry changed)
	$(UV_RUN) python -m plotter_cad fem-status

diff:  ## Parts changed between revisions: REV_A=HEAD REV_B=WORKTREE (defaults); add ARGS=--all
	$(UV_RUN) python -m plotter_cad diff $(REV_A) $(REV_B) $(ARGS)
