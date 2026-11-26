# Coding standards

How code is written in this repository: style, preferred patterns, CAD conventions and testing.
They apply to everyone, human or AI agent, and to both packages, `plotzker` and `cadder`.
The project's goals, design and working process are in [`README.md`](README.md).

**Contents:** 1 Language and style · 2 Code structure and design · 3 Type annotations ·
4 Comments and docblocks · 5 CAD conventions · 6 2D sketches · 7 Testing

---

## 1. Language and style

- **US English spelling** everywhere: docs, comments, docstrings, identifiers, sketch
  comments (center, color, modeled, leveling, aluminum, millimeter, catalog...).
- PEP 8, enforced by `ruff format` and `ruff check` (config in `pyproject.toml`, and in
  `cadder/pyproject.toml` for cadder; line length 119).
- No star imports (`from x import *`): import names explicitly
  (`from pythonscad import cube, cylinder`). The one exception is a package `__init__`
  republishing another package's whole public API, marked `# noqa: F403` with the reason.
  Enforced by ruff (F403, F405).
- Don't parenthesize a returned tuple that fits on one line: `return x, y`, not
  `return (x, y)`. Parentheses stay where a tuple spans several lines.
- **Names favor readability over brevity.** Spell words out (`height`, `outer_dia`,
  `thickness`, not `h`, `od`, `t`), including in dataclass fields and parameters. Engineering
  shorthand is not an exception. Don't copy a module constant into a shorter local name; use
  the constant's own name. One or two letters are fine only in a very narrow scope
  (comprehensions, short loops, temporaries) or where the short name is the convention, such
  as coordinate letters (`x`, `y`, `z`, `u`, `v`). The wider the scope, the more descriptive
  the name. Allowed abbreviations: names set by a library (such as PythonSCAD's `fn`),
  `min`, `max`, `id`, `dia` (diameter), `tol` (tolerance), `rect` (rectangle) and unit
  suffixes (`_mm`, `_mpa`, `_g`, `_deg`). Names that belong to a file format or external
  interface (CPSK, TOML keys, `--json` output, the CLI) keep their spelling.
- Mark assumed values with an `ASSUMED` comment, design choices with `DESIGN (Tn.m)`.
- **Command-line tools use [Typer](https://typer.tiangolo.com)** (a project dependency): arguments
  and options from type-annotated function parameters, output with `typer.echo` / `typer.secho`
  (errors to stderr with `err=True`, failures as `raise typer.Exit(code)`), not `argparse`, `click`
  or bare `print` / `sys.exit`. Exception: scripts that run in a limited environment without our
  dependencies (the FreeCAD Python, code embedded in a PythonSCAD subprocess): there keep to the
  standard library.

## 2. Code structure and design

- Entry-point code runs only under a guard, `if __name__ == "__main__":`, so importing a
  module never runs it. A script run by `freecadcmd` uses
  `if __name__ in ("__main__", "<file name>"):` and ends a failure with `sys.exit(1)`.
  Exception: files a host application is meant to run on load (FreeCAD's `Init.py`,
  `preview.py`).
- **Flat is better than nested.** Write functions at module level, prefixed with `_` when
  private to the module. Nest a function only if it is short (up to 8 lines) and is one of:
  - a local callable used right where it is defined, such as in a comprehension or as `key=`;
  - a closure that updates enclosing state, such as a `nonlocal` counter or a signal or event
    handler;
  - glue that gives an API callback extra context (prefer `functools.partial`, or a lambda
    if it is one line with no logic);
  - a mock or monkeypatch replacement in a test.

  The length limit does not apply to the function a decorator or factory builds and returns,
  when there is little code outside it.
- Don't give a local variable or parameter the name of something at module level (an import,
  function, class or variable). Pytest fixtures requested as parameters are the exception.
  Enforced by `tests/test_code_rules.py`.
- **Prefer polymorphism to type checks.** Behavior that depends on an object's class, or
  mainly works on its data, is a method of that class, and subclasses extend or override it.
  Treat `isinstance` on our own classes as a code smell. A method must not pull a higher
  layer into the class (a solver, an exporter, a renderer or the CLI): code there that
  dispatches on type uses `match`. `isinstance` is fine for validating outside input, for
  built-in and library types, and for picking out members of a mixed collection.
- Don't give a function the same name as its module inside a package `__init__`
  (`from .x_carriage import x_carriage` shadows the submodule); import modules there.

## 3. Type annotations

- All code must pass type checking with `mypy` (`make typecheck`, part of `make check`;
  strict mode, config in `pyproject.toml`). Annotate all new functions and public
  attributes.
- Follow PEP 604 (`X | Y` unions) and PEP 673 (`Self`).
- Use `collections.abc` for generic collection types over deprecated `typing` types.
- Prefer structural typing (duck typing) such as `Protocol`s over strict inheritance,
  unless inheritance also serves other purposes beyond type adherence (such as code reuse).
- `pythonscad` ships no type information: the stub `cadder/stubs/pythonscad/__init__.pyi`
  provides it, including the `Solid` type. `Solid` exists only in the stub, so import it
  under `if TYPE_CHECKING:` (annotations are lazy in Python 3.14). Extend the stub when
  using a new PythonSCAD function or method.

## 4. Comments and docblocks

- Files, classes and functions have a short docblock (at least a one-liner, PEP 257 style)
  describing the purpose of the unit: "what this is", not "how this works".
- A Google-style docstring may describe a function in more detail, beyond what naming and
  type annotations already say, if necessary.
- Inline comments should be rare, and never explain what the code does or repeat what is
  obvious from reading it.
- A short inline comment is fine for a non-obvious block or something others may find
  confusing or counter-intuitive, but code should be self-documenting; a comment is a
  last resort.

## 5. CAD conventions (PythonSCAD)

The CAD is a Python package, `plotzker` (`src/plotzker/`), built on the
[PythonSCAD](https://pythonscad.org) `pythonscad` module (OpenSCAD's geometry engine
with a native Python API) and on **cadder** (`cadder/`, D36), the generic framework for
software-driven CAD projects. Setup and commands are in README §6.

- **Where code goes:** anything another CAD project could use as is (a helper, a part or
  assembly class, a vendor part, a check, an export) belongs in `cadder`; anything about
  this machine (its dimensions, parts, loads, layout) belongs in `plotzker`. **cadder never
  imports plotzker** (ruff rule TID251 and a test enforce it); cadder's tests use their own
  fixture project (`cadder/tests/fixture`). A change to cadder needs a cadder test.
- **Environment:** set up as in README §6; run commands in the activated `.venv` or with `uv run`.
  Don't install packages with `pip`; add them to the `pyproject.toml` of the package that needs
  them (cadder's own in `cadder/`) and re-sync.
- **Parametric first.** Shared dimensions in `params.py` (travel, shaft spacing,
  clearances, tolerances, tool-plate interface), grouped into frozen dataclasses with one
  module-level instance each (`TOL`, `BEAM`, `CARRIAGE`, `TOOL_PLATE`...). Vendor-part
  dimensions and simple models in `cadder.hardware` (`SK10_SPEC`, `SCS10UU_SPEC`, `NEMA17_SPEC`, `VWHEEL_SPEC`,
  fasteners...); plotter-specific hardware in `plotzker.hardware`. Derived values are
  `@property`s, never typed-in numbers. No magic numbers in part modules: add a parameter
  instead.
- **Design rules** live in `params.design_checks()` (`(ok, message)` pairs);
  `check_design()` raises `cadder.checks.DesignError`. Add a rule whenever a new
  constraint appears (clearance, travel, fit).
- One printable part per module in `parts/`, exposing a function that returns the part
  in its **print orientation** (flat face on z = 0), plus `*_installed()` / `*_left()`
  helpers when the part is designed in another frame. Register every part in
  `parts.PARTS` (name = STL file name): a `cadder.part.PrintedPart` once it has a print
  profile, material and FEM data (README §7.6), a plain `Part` until then. A non-printed part of
  a known material (a plate, a purchased part in a check) is a `MaterialPart`.
- Assemblies in `assemblies/` return lists of colored solids (parts + hardware models)
  for fit checks; register them in `assemblies.ASSEMBLIES` as `cadder.assembly.Assembly`
  objects. The FreeCAD assembly (rigid bodies and joints) is defined in
  `freecad_assembly.py` (`cadder.freecad`).
- Print tolerances: `params.TOL`, a `cadder.printing.Tolerances` with cadder's defaults
  and the values measured on our prints (tune after a test print):
  - Bolt clearance holes: nominal + 0.3–0.4 mm (M3 → 3.4 mm, M5 → 5.4 mm)
  - Sliding fit +0.2 mm; press fit −0.1 to 0 mm
  - Nut traps: across-flats + 0.3 mm
  - Minimum wall: 1.6 mm (4 perimeters at 0.4 mm nozzle)
- **Handles:** a part that hardware or other parts attach to exposes named handles
  (`cadder.handles.set_handles` / `get_handle`) and assemblies place things with `.align(handle)`
  rather than repeating the part's coordinates (D28).
- **Nut slots pressed in from an edge** (a nut slid in sideways): use
  `cadder.printing.nut_slot(size, reach, axis, entrance, tol=TOL)`. The nut goes in **flat-first** (a flat faces the pressing
  direction, so a thumb pushes straight onto it instead of rotating a pointy nut), and the
  pocket follows the hex outline at the bottom (flat floor, 60° sloped sides up to the
  corners) so the nut **cannot turn** when the bolt is tightened; above the corners the walls
  run straight out to the entrance. A plain rectangular slot wide enough for the corners lets
  the nut spin. Hex shafts (nut seated along its axis) use `TOL.nut_trap_across_corners` /
  `nut_trap_height` instead. Measured on PETG: slots come out ~0.1 mm narrower across and ~0.1 mm
  thicker than designed (`TOL.nut_slot`, `TOL.nut_thickness` allow for it).
- Prefer designs printable without supports (teardrop holes from `cadder.geometry`, 45°
  overhangs); note any required supports in the module docstring.
- Each part module starts with a docstring: purpose, required hardware (with
  quantities), print settings (material, layer height, infill, orientation). A part defined as a
  `PrintedPart` (README §7.6) names its print profile instead of repeating the settings.
- Facet counts: pass `fn=` explicitly; use `cadder.geometry.FN` / `FN_HOLE` (64) for
  printed geometry, lower counts only for hardware models.
- Prefer the method style for transforms (`cube(...).rotate(...).translate(...)`): it
  reads in the order the operations happen. Note that this is the reverse of the
  OpenSCAD nesting order.

## 6. 2D sketches

On trial (D23): a shape that is easier to draw than to code can be an
SVG file next to the Python module that uses it. `cadder.geometry.load_sketch(path)` imports it
as a 2D object, which the module extrudes:

```python
profile = load_sketch(Path(__file__).with_name("vslot_2040.svg"))
beam = linear_extrude(profile, height=520)
```

- Draw at **1 user unit = 1 mm**: `width`/`height` in mm and a `viewBox` with the same
  numbers. The viewBox's bottom-left corner is the CAD origin; the sketch keeps the
  orientation it is drawn in.
- Every shape is imported **filled**; strokes and colors are ignored and separate
  shapes are unioned. Make holes sub-paths of one `<path>` with `fill-rule="evenodd"`
  (Inkscape: *Path → Combine*). Convert text and clones to paths.
- A profile used at several lengths is loaded directly (`vslot_x(length, size)` picks
  the 2020 or 2040 sketch). A part with fixed 3D dimensions gets a module with the same
  name as its sketch (`foo.svg` + `foo.py`) that extrudes it.
- The sketches can be edited in Inkscape or as text; note the dimensions in a comment at
  the top of the file.
- Parametric/constrained sketches: draw them in your CAD tool (e.g. FreeCAD) and export
  the solved outline as SVG into the repo (D24); the SVG is the source for PythonSCAD.

## 7. Testing

Tests exist to make changes faster and safer: they should fail when the code is broken
and stay quiet when a design value changes on purpose. A test that only makes changes
slower has negative value; delete it.

**Test:**
- Pure functions that are reused or more than trivial (geometry helpers, the sketch
  loader, the measuring helpers in `cadder.testing`).
- cadder's tests (`cadder/tests/`) run against the fixture project, never against the
  plotter; the plotter's tests (`tests/`) cover its own parts, assemblies and specs.
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
