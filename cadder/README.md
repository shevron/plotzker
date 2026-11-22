# cadder

A framework for **software-driven CAD projects** written for
[PythonSCAD](https://pythonscad.org): a project describes its parts, assemblies and checks in
plain Python, and cadder exports them (STL, renders, FreeCAD assemblies, 1:1 drawings), checks
them (design rules, FEM) and compares revisions (a visual design diff).

It is developed inside the [plotzker](https://github.com/shevron/plotzker) repository (a DIY
pen plotter, its first user) as a uv workspace member, and will move to its own repository.
cadder never imports a project; its tests use their own fixture project (`tests/fixture`).

## A project

A project is a Python package with a `cadder.project.Project`, named in its `pyproject.toml`:

```toml
[tool.cadder]
project = "mypackage.project:PROJECT"
```

```python
from cadder.project import Project

PROJECT = Project(
    name="mypackage",
    spec="mypackage.project:PROJECT",
    root=Path(__file__).resolve().parents[2],  # the repository
    parts=lambda: PARTS,  # name -> Part
    assemblies=lambda: ASSEMBLIES,  # name -> Assembly
    assembly_checks=lambda: ASSEMBLY_CHECKS,  # name -> AssemblyCheck (FEM across parts)
    freecad_assemblies=lambda: {"Machine": MACHINE},
    design_checks=design_checks,  # yields (ok, message)
    report=key_numbers,  # text printed by `check`
    commands=add_my_commands,  # extra Typer commands
    params_file="src/mypackage/params.py",  # shown next to changed parts in the diff
)
```

The registries are functions, so the command line starts without building any geometry. The
demo project in [`tests/fixture/src/demo/project.py`](tests/fixture/src/demo/project.py) is a
complete small example.

## Building blocks

| Module | What it gives a project |
|---|---|
| `cadder.part` | `Part` (name, description, geometry in output orientation; `stl` to export it) → `MaterialPart` (material, material axis, analysis frame and geometry, FEM spec: load cases, supports, displacement limits) → `PrintedPart` (print profile, build direction) |
| `cadder.assembly` | `Assembly` (parts and hardware placed for a fit check and render), `AssemblyCheck` (FEM budget across parts: their deflections plus the play between them) |
| `cadder.freecad` | `FreeCadAssembly` with `Component`s, rigid `Body`s and `Joint`s (Slider, Revolute, ...); exported with shared STLs for congruent components and built into an `.FCStd` by FreeCAD 1.x |
| `cadder.handles` | Named 4×4 frames on solids (`set_handles`, `get_handle(s)`, `handle`, `frame_handle`, `shift_handle`, `place_in_frame`) so assemblies place parts with `.align(handle)` |
| `cadder.geometry` | Facet settings (`FN`, `CADDER_FN`), `box`, teardrop holes, the SVG sketch loader `load_sketch`, small vector helpers |
| `cadder.printing` | `Tolerances` for FDM prints (clearance holes, nut traps, fits) and `nut_slot`, a hex pocket for a nut pressed in sideways |
| `cadder.hardware` | Vendor parts with dimensions and simple models: metric fasteners, bearings, GT2 belts/pulleys/idlers, NEMA17 and a micro servo, V-slot extrusions (SVG profiles) with wheels and eccentric spacers, smooth shafts, SK10, SCS10UU |
| `cadder.materials` | `Material`, `PrintProfile` and `MaterialLibrary`, which reads a project's materials TOML and print profiles folder |
| `cadder.regions` | `Box` / `Cylinder` regions that select faces and nodes for loads, supports and limits; `Placement` |
| `cadder.checks` | `DesignError`, `run_design_checks` |
| `cadder.drawing` | `SvgDrawing` (1:1 sheets in mm with y up: drilling templates, cutting layouts) and `markdown_table` |
| `cadder.fem` | The FEM check (needs FreeCAD's gmsh and CalculiX): STL cleaning, meshing, CalculiX, failure index, verdicts with spec and geometry hashes, reports and pictures |
| `cadder.diff` | The design diff between git revisions: per-revision snapshots, part and assembly comparison, a self-contained HTML report with a 3D viewer |
| `cadder.render` | STL export and PythonSCAD renders (normal and all-sides inspection views) |
| `cadder.testing` | Measurements on solids for a project's tests: volume, bounding box, shells, touching, connected groups |
| `cadder.cli` | The command line, and `make_app` / `run` for a project's own entry point |

## Command line

`cadder COMMAND` in a project's repository (or `cadder --project SPEC COMMAND`):

| Command | What it does |
|---|---|
| `check` | Design checks and the project's key numbers |
| `stl [NAMES]` | Export parts (those with `stl` set) to `stl/` |
| `render [NAMES] [--inspect]` | PNGs of parts and assemblies (needs the PythonSCAD app) |
| `part [--list] [NAME] [--json] [--stl PATH]` | A part's material, profile and FEM specification |
| `fem NAMES... [--viz]` | FEM check of parts and assembly checks; results in `fem/results/`, verdicts in `fem/verdicts.toml` |
| `fem-status` | FEM state of every part; stale verdicts flagged |
| `diff [A [B]]` | What changed between two git revisions (default `HEAD` → working tree) |
| `freecad [NAMES] [--export-only]` | Build the project's FreeCAD assemblies into `freecad/<name>.FCStd` |
| `all` | `check`, `stl`, the project's extra outputs (`Project.all_steps`), `render` |

A project adds its own commands through `Project.commands`, and can offer its own entry point
(`python -m mypackage`) with `cadder.cli.run(PROJECT)`.

Environment: `CADDER_FN` lowers the facet count (the FEM export uses 20);
`CADDER_FREECAD_BIN_DIR` points to FreeCAD's `bin` folder (`ccx`, `gmsh`, `freecadcmd`; default:
`/Applications/FreeCAD.app/Contents/Resources/bin`); `PYTHONSCAD` to the PythonSCAD app.

## Development

```bash
uv sync --extra dev --extra diff     # from the workspace root, or here
uv run python -m pytest              # cadder's tests (tests/, on the fixture project)
uv run mypy && uv run ruff check .   # strict types and lint; `plotzker` imports are banned (TID251)
```

The `diff` extra (numpy, manifold3d) is needed for the design diff. Conventions (code style,
typing, testing) are those of the plotzker repository's README §7 for now; they move here with
cadder.
