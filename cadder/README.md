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
| `cadder.geometry` | Facet settings (`FN`, `CADDER_FN`), `box`, teardrop holes, the sketch loader `load_sketch` (SVG, and CPSK files solved with `params` overrides), small vector helpers |
| `cadder.cpsk` | CPSK parametric sketches ([spec](docs/cpsk/spec-0.1.md)): everything in `cpsk_core`, plus `solve` (FreeCAD's PlaneGCS solver through `planegcs`; degrees of freedom, redundant and conflicting constraints as diagnostics; `strict`), `to_svg` (a profile for `load_sketch`) |
| `cpsk_core` | The CPSK format without a solver, standard library only and Python ≥ 3.11 so FreeCAD's Python can use it: the lossless `Document` (parse, build, canonical `write`, canonical constraint placement `nest_constraints`), `load`/`loads`/`compile_document` (validation, nesting, formulas, variable overrides) into a `Sketch` |
| `cpsk_freecad` | The FreeCAD addon's package (`freecad-addon/CPSK/`, runs in FreeCAD's Python; not in the wheel): `export_sketch` writes a Sketcher sketch as a `.cpsk` file, refusing unsupported features with a list; `import_sketch` creates a sketch and its VarSet from one; ids, names and metadata survive both round trips. The addon (`Init.py`, `importCPSK.py`) adds `.cpsk` to FreeCAD's File > Open, Import and Export; `make freecad-addon` installs it ([plan](docs/cpsk/freecad-plugin-plan.md)) |
| `cadder.printing` | `Tolerances` for FDM prints (clearance holes, nut traps, fits) and `nut_slot`, a hex pocket for a nut pressed in sideways |
| `cadder.hardware` | Vendor parts with dimensions and simple models: metric fasteners, bearings, GT2 belts/pulleys/idlers, NEMA17 and a micro servo, V-slot extrusions (SVG profiles) with wheels and eccentric spacers, smooth shafts, SK10, SCS10UU |
| `cadder.materials` | `Material`, `PrintProfile` and `MaterialLibrary`, which reads a project's materials TOML and print profiles folder |
| `cadder.regions` | `Box` / `Cylinder` regions that select faces and nodes for loads, supports and limits; `Placement` |
| `cadder.checks` | `DesignError`, `run_design_checks` |
| `cadder.drawing` | `SvgDrawing` (1:1 sheets in mm with y up: drilling templates, cutting layouts) and `markdown_table` |
| `cadder.fem` | The FEM check (needs FreeCAD's gmsh and CalculiX): STL cleaning, meshing, CalculiX, failure index, verdicts with spec and geometry hashes, reports and pictures |
| `cadder.diff` | The design diff between git revisions: per-revision snapshots, part and assembly comparison, a self-contained HTML report with a 3D viewer |
| `cadder.render` | STL export and PythonSCAD renders (normal and all-sides inspection views) |
| `cadder.photo` | Measuring parts from photos: a printed ChArUco target, rectification (camera pose, scale, perspective), sub-pixel edges and holes in mm, parallax correction, a feature file drawn back onto the photo (`photo` extra) |
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
| `photo COMMAND` | Measure parts from photos: `target`, `info`, `convert`, `rectify`, `crop`, `edges`, `holes`, `point`, `overlay`, `table` (also `python -m cadder.photo`; needs the `photo` extra) |

Guides: [FEM checks](docs/fem.md), [design diff](docs/diff.md), [photos](docs/photo.md),
[FreeCAD assemblies](docs/freecad.md), [CPSK sketch format](docs/cpsk/spec-0.1.md) (draft),
[CPSK FreeCAD addon](freecad-addon/CPSK/README.md); background:
[parametric sketch formats](docs/sketch-formats.md), [CPSK RFC](docs/rfc/parametric-sketch-format.md).

A project adds its own commands through `Project.commands`, and can offer its own entry point
(`python -m mypackage`) with `cadder.cli.run(PROJECT)`.

Environment: `CADDER_FN` lowers the facet count (the FEM export uses 20);
`CADDER_FREECAD_BIN_DIR` points to FreeCAD's `bin` folder (`ccx`, `gmsh`, `freecadcmd`; default:
`/Applications/FreeCAD.app/Contents/Resources/bin`); `PYTHONSCAD` to the PythonSCAD app.

## Development

```bash
uv sync --extra dev --extra diff --extra photo   # from the workspace root, or here
uv run python -m pytest              # cadder's tests (tests/, on the fixture project)
uv run mypy && uv run ruff check .   # strict types and lint; `plotzker` imports are banned (TID251)
make test-cpsk-core                  # (workspace root) cpsk_core's tests on FreeCAD's Python 3.11
make freecad-addon                   # (workspace root) link the CPSK addon into FreeCAD's Mod folder
```

The `diff` extra (numpy, manifold3d) is needed for the design diff, the `photo` extra (OpenCV,
Pillow, pillow-heif) for `cadder photo`. `planegcs` (the CPSK
solver) has no macOS wheels; it builds from source with Eigen and Boost (`brew install eigen boost`). Conventions (code style,
typing, testing) are those of the plotzker repository's README §7 for now; they move here with
cadder.
