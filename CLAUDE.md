# CLAUDE.md — guidelines for working on the DIY Pen Plotter

`README.md` is the single source of truth: requirements (§1), inventory (§2), build
phases (§3), design (§4), key numbers (§5), decision log (§6), open questions (§7) and
the **work plan (§8)**. This file says *how* to work on the project.

## Starting a session

1. Read `README.md`: the status line, §5 key numbers, §6 decisions, and the §8 task being
   worked on. Read the linked `docs/` files the task needs (`docs/controller.md` for
   electronics/firmware, `docs/hardware.md` for part dimensions).
2. Work on **one §8 task at a time**, unless the user asks otherwise. Check its "done when"
   criterion.
3. Before designing around an unknown dimension or fact, ask the user to measure or check
   it (photos welcome).

## Finishing a session

- Tick the task in §8; add follow-up tasks if any came up.
- Record new or changed decisions in §6 (and open questions in §7); update §2, §5 and
  `docs/` with any new facts or measurements.
- Update the README status line.
- Keep files on the user's computer in sync: after writing a file there, check it
  actually updated (size/timestamp). Re-send it if not.

## Hard rules

1. **Metric only.** Millimeters, degrees, mm/s (or mm/min where G-code requires it, and
   say which). No imperial units or fasteners.
2. **Hardware is off-the-shelf or salvaged 3D-printer parts.** Metric hex fasteners
   (M2.5/M3/M4/M5, ISO 4762 socket head preferred), heat-set inserts or captive nuts,
   NEMA17 steppers, GT2 belts/pulleys, T8 lead screws, 608/625 bearings, LM6UU/LM8UU,
   Ø10 mm shafts with SK10 supports and SCS10UU blocks, 2020/2040/4020/4040 V-slot extrusion.
   Anything else must be justified and noted in the README.
3. **CAD is PythonSCAD (Python).** The `plotter_cad` package under `src/` is the only CAD
   source (D2, D22). No other CAD formats as sources, with one exception on trial (D23):
   2D sketches as SVG files next to the module that extrudes them (README §10). STLs and renders are generated
   outputs.
4. **Check the inventory (README §2) and `docs/hardware.md` before designing around a
   part.** If a dimension is unknown, ask the user. Mark any assumed value clearly as
   `ASSUMED` in code and as *assumed* in docs.
5. **Don't silently change a decision.** Decisions live in README §6. To change one,
   propose it, explain the trade-off, and update the log once the user agrees.
6. **Safety:** printer heaters stay disabled in firmware and unconnected; mains wiring
   enclosed and earthed.

## Design constraints to keep in mind

- **Keep the gantry light.** The Y shafts are end-supported Ø10 mm shafts that sag
  ~0.2–0.4 mm under the gantry (README §4.2).
- **Pen head:** ≥ 5 mm lift, ≥ 3 mm float with near-constant pressure, ~20 mm manual
  height adjustment, 7–16 mm pens, pen close to the carriage face (README §4.3, §4.4).
- **Modularity:** tool heads attach only through the tool-plate interface (hook + 2 × M3,
  README §4.4). Don't couple tool-head geometry to the carriage beyond that interface.
- **Clearance:** 15 mm media must pass under the head and gantry everywhere in the travel.
- **Simplicity over performance:** prefer the easy-to-build, easy-to-debug option.
- **Serviceability:** belts tensionable without disassembly; motors, boards and tool
  heads replaceable with hand tools.

## Documentation

- Keep the README concise; prefer tables for comparisons and decisions.
- **US English spelling** everywhere: docs, comments, docstrings, identifiers, sketch
  comments (center, color, modeled, leveling, aluminum, millimeter, catalog...).
- Longer research, procedures and results go in `docs/<topic>.md` (e.g.
  `docs/pen-lift.md`, `docs/calibration.md`), linked from the README.
- Don't store vendor datasheets or drawings in the repository (copyright). Record the
  values for the specific parts we use in `docs/hardware.md` and note where they came from.
- Electronics wiring and pin allocation live in `docs/controller.md`; keep it current
  (mark items verified after bench tests).

## CAD conventions (PythonSCAD)

The CAD is a Python package, `plotter_cad` (`src/plotter_cad/`), built on the
[PythonSCAD](https://pythonscad.org) `pythonscad` module (OpenSCAD's geometry engine
with a native Python API). Setup and commands are in README §10.

- **Environment:** Python ≥ 3.14 from pyenv (`.python-version`), virtualenv in `.venv`,
  dependencies managed by uv (`uv sync --extra dev`, locked in `uv.lock`). Run commands
  in the activated `.venv` or with `uv run` (e.g. `uv run python -m pytest`). Don't
  install packages with `pip`; add them to `pyproject.toml` and re-sync. `Makefile`
  shortcuts: `make develop`, `make check` (mypy + ruff, read-only), `make typecheck` (mypy), `make format`, `make lint` (ruff with
  fixes), `make test` (pytest), `make stl`, `make render`,
  `make clean`.

- **Parametric first.** Shared dimensions in `params.py` (travel, shaft spacing,
  clearances, tolerances, tool-plate interface), grouped into frozen dataclasses with one
  module-level instance each (`TOL`, `BEAM`, `CARRIAGE`, `TOOL_PLATE`...). Vendor-part
  dimensions and simple models in `hardware/` (`SK10`, `SCS10UU`, `NEMA17`, `VWHEEL`,
  fasteners...). Derived values are `@property`s, never typed-in numbers. No magic
  numbers in part modules: add a parameter instead.
- **2D sketches (trial, D23):** an SVG next to the module that uses it, loaded with
  `geometry.load_sketch()`; 1 unit = 1 mm, origin at the viewBox's bottom-left, holes as
  `evenodd` sub-paths, dimensions noted in a comment in the file (README §10). So far
  only for vendor-part profiles (`hardware/vslot_*.svg`); printed parts stay parametric
  in Python unless the user asks for a sketch.
- **Design rules** live in `params.design_checks()`; `check_design()` raises
  `DesignError`. Add a rule whenever a new constraint appears (clearance, travel, fit).
- One printable part per module in `parts/`, exposing a function that returns the part
  in its **print orientation** (flat face on z = 0), plus `*_installed()` / `*_left()`
  helpers when the part is designed in another frame. Register every printable part in
  `parts.PRINTABLE_PARTS` (name = STL file name).
- Assemblies in `assemblies/` return lists of colored solids (parts + hardware models)
  for fit checks; register them in `assemblies.ASSEMBLIES`.
- Default print tolerances (tune after a test print; keep them in `params.TOL`):
  - Bolt clearance holes: nominal + 0.3–0.4 mm (M3 → 3.4 mm, M5 → 5.4 mm)
  - Sliding fit +0.2 mm; press fit −0.1 to 0 mm
  - Nut traps: across-flats + 0.3 mm
  - Minimum wall: 1.6 mm (4 perimeters at 0.4 mm nozzle)
- Prefer designs printable without supports (teardrop holes from `geometry.py`, 45°
  overhangs); note any required supports in the module docstring.
- Each part module starts with a docstring: purpose, required hardware (with
  quantities), print settings (material, layer height, infill, orientation).
- Facet counts: pass `fn=` explicitly; use `geometry.FN` / `geometry.FN_HOLE` (64) for
  printed geometry, lower counts only for hardware models.
- **Before handing over a CAD change:** `python -m pytest` and `ruff check` pass;
  `python -m plotter_cad stl` regenerates `stl/`; `python -m plotter_cad render`
  regenerates `renders/` (needs the PythonSCAD app). If geometry changed on purpose,
  review the STLs/renders.

## Python coding standards

- PEP 8, enforced by `ruff format` and `ruff check` (config in `pyproject.toml`,
  line length 100).
- Import PythonSCAD names explicitly (`from pythonscad import cube, cylinder`), never
  `from pythonscad import *`.
- Prefer the method style for transforms (`cube(...).rotate(...).translate(...)`): it
  reads in the order the operations happen. Note that this is the reverse of the
  OpenSCAD nesting order.
- Don't give a function the same name as its module inside a package `__init__`
  (`from .x_carriage import x_carriage` shadows the submodule); import modules there.
- Mark assumed values with an `ASSUMED` comment, design choices with `DESIGN (Tn.m)`.
- (More project-specific guidelines will be added here over time.)

#### Type annotations

- All code must pass type checking with `mypy` (`make typecheck`, part of `make check`;
  strict mode, config in `pyproject.toml`). Annotate all new functions and public
  attributes.
- Follow PEP 604 (`X | Y` unions) and PEP 673 (`Self`).
- Use `collections.abc` for generic collection types over deprecated `typing` types.
- Prefer structural typing (duck typing) such as `Protocol`s over strict inheritance,
  unless inheritance also serves other purposes beyond type adherence (such as code reuse).
- `pythonscad` ships no type information: the local stub `stubs/pythonscad/__init__.pyi`
  provides it, including the `Solid` type. `Solid` exists only in the stub, so import it
  under `if TYPE_CHECKING:` (annotations are lazy in Python 3.14). Extend the stub when
  using a new PythonSCAD function or method.

#### Comments and docblocks

- Files, classes and functions have a short docblock (at least a one-liner, PEP 257 style)
  describing the purpose of the unit: "what this is", not "how this works".
- A Google-style docstring may describe a function in more detail, beyond what naming and
  type annotations already say, if necessary.
- Inline comments should be rare, and never explain what the code does or repeat what is
  obvious from reading it.
- A short inline comment is fine for a non-obvious block or something others may find
  confusing or counter-intuitive, but code should be self-documenting; a comment is a
  last resort.

## Testing

Tests exist to make changes faster and safer: they should fail when the code is broken
and stay quiet when a design value changes on purpose. A test that only makes changes
slower has negative value; delete it.

**Test:**
- Pure functions that are reused or more than trivial (geometry helpers, the sketch
  loader, the measuring helpers in `tests/solids.py`).
- Solids are sane: every printable part is one piece with no enclosed voids, has a
  plausible volume and rests on the print bed.
- Assemblies hold together: parts touch what they mount on, nothing floats.
- Behavior at the public interface: the design rules pass, a broken rule is reported,
  errors for bad input, the STL export writes its files.

**Don't test:**
- Parameter or geometry values that are expected to change (key numbers, reference
  volumes or bounding boxes). That duplicates the configuration and breaks on every
  intended change. A real constraint belongs in `params.design_checks()` instead.
- Trivial behavior: Python operators, one-line arithmetic, other libraries.
- Implementation details and private (`_name`) code.
- Anything through a mock that replaces the code under test. Overriding a parameter
  set (e.g. `dataclasses.replace` on a params instance) is fine; faking the
  implementation is not.

Run with `make test`. Assemblies are fit-check models: when a connection test fails
because a model is too crude (a missing nut or bushing), fix the model.

## Firmware

- Marlin 2.1.x, `BOARD_ZRIB_V53`. Keep the configuration under `firmware/` (full files or
  a diff against a stated Marlin version) with build and flash notes.
- Never enable heaters or thermal outputs.

## Working style

- When comparing options, give a short table of trade-offs and a recommendation.
- Ask the user for physical facts (measurements, part markings, photos) rather than guessing.
- Deliver results the user can use directly: files in the project folder, plus a short
  summary of what changed and what's next.
