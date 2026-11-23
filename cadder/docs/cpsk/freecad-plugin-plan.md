# Plan: FreeCAD import/export plugin for CPSK

| | |
|---|---|
| **Status** | Plan accepted (decisions D1–D9: 2026-11-23). Phases 0 ([results](freecad-conventions.md)) to 4 done |
| **Date** | 2026-11-23 |
| **Implements** | [RFC](../rfc/parametric-sketch-format.md) §4 step 3 and §8; [spec 0.1](spec-0.1.md) |
| **Target** | FreeCAD 1.1 (installed here: 1.1.3, Python 3.11.14) |

## 1. Goal

A FreeCAD addon that exports a Sketcher sketch to a `.cpsk` file and imports a `.cpsk` file as a
Sketcher sketch, so that sketches can be drawn and edited visually and consumed by cadder
(`load_sketch`).

Requirements, from RFC §8:

- **R1.** Geometry: points, lines, circles and arcs (spec §7). Ellipses and B-splines are out of
  scope for 0.1.
- **R2.** External geometry is exported as ordinary geometry.
- **R3.** Sketcher expressions are converted to CPSK formulas. An expression that cannot be
  converted is an unsupported feature.
- **R4.** The plugin refuses to export a sketch with unsupported features and lists them.
- **R5.** FreeCAD → CPSK → FreeCAD is lossless for the supported feature set.

Not goals for this plan: sketch placement and attachment in 3D (spec non-goal), editing CPSK
files inside FreeCAD without importing them, and an Addon Manager release (§7, phase 5).

## 2. Facts that shape the design

Checked with `freecadcmd` on FreeCAD 1.1.3:

| Fact | Consequence |
|---|---|
| FreeCAD's Python is **3.11**; `cadder.cpsk` uses 3.12+ syntax (`type` aliases, unquoted forward references) and imports `planegcs` | The plugin cannot import `cadder.cpsk` as it is (decision D1) |
| A constraint is `Sketcher.Constraint` with `Type`, `First`/`FirstPos`, `Second`/`SecondPos`, `Third`/`ThirdPos`, `Value`, `Name`, `Driving`, `IsActive`. Unused GeoIds are -2000 | Mapping in §4 is by (Type, which GeoIds/PosIds are set) |
| GeoIds: -1 is the horizontal axis, -2 the vertical axis, ≤ -3 external geometry. The root point is (-1, PosId 1). PosId: 0 edge, 1 start, 2 end, 3 center | `origin`, `x_axis`, `y_axis` map directly |
| Expressions live in `ExpressionEngine` as `('.Constraints.<name>', '<expression>')` | Only named constraints can carry expressions, matching CPSK, where formulas reference constraint ids |
| A tangent between end points stores an angle in `Value` (e.g. -π/2): FreeCAD's locked tangency direction | Export ignores it (CPSK derives it from stored coordinates, as the reader does); import adds the constraint without a value and FreeCAD sets it (verified in phase 0) |
| `App::VarSet` exists (FreeCAD ≥ 1.0) | Candidate home for CPSK variables (decision D2) |
| The sketch reports `FullyConstrained`, `ConflictingConstraints`, `RedundantConstraints`, `MalformedConstraints` | Export can warn about the same problems the CPSK solver reports |
| User addons go to `~/Library/Application Support/FreeCAD/v1-1/Mod/` (macOS) | Installation target (phase 4) |

## 3. Architecture

```
cadder/
  src/cpsk_core/            (D1: pure standard library, Python ≥ 3.11)
    document.py             lossless document model: variables with formula text, primitives,
                            nested and top-level constraints, metadata, extension content
    reader.py, formula.py   parsing, references, nesting, evaluation (moved from cadder.cpsk)
    writer.py               canonical writer (spec §11.4: nested placement, number format)
  src/cadder/cpsk/          solver (planegcs) and SVG export, on top of cpsk_core
  freecad-addon/CPSK/       the FreeCAD addon (runs in FreeCAD's Python)
    Init.py, InitGui.py     registers File > Import / Export types
    package.xml             addon metadata (Addon Manager format)
    cpsk_freecad/
      export_sketch.py      SketchObject → cpsk_core.Document
      import_sketch.py      cpsk_core.Document → SketchObject (+ VarSet)
      expressions.py        FreeCAD expression ↔ CPSK formula
      unsupported.py        feature checks and the report shown to the user
```

The addon does not solve CPSK documents itself: FreeCAD's Sketcher solves them after import, and
the stored coordinates come from FreeCAD's solved geometry on export.

A **lossless document model** is the main new piece. Today `cadder.cpsk.Sketch` holds evaluated
values only, which is enough to solve but not to write a file back: formulas, variable limits,
descriptions, metadata and extension content are lost. Both directions of the plugin, and any
future CPSK editor or formatter, need it.

**As built (phase 1):** `cpsk_core` lives in `cadder/src/cpsk_core/` and ships in the cadder
distribution. The lossless model is an element tree (`Element`, `Comment`, `Document`) rather
than typed classes per element: it keeps attribute order, comments, unknown CPSK content and
extensions without special cases, and `cpsk_core.element()` builds elements in code. The
writer's canonical layout is described in `cpsk_core.document.write`; the spec example is in that
layout. Solving moved from `Sketch.solve()` to `cadder.cpsk.solve(sketch)`.

**As built (phase 2):** the addon's package is `cadder/freecad-addon/CPSK/cpsk_freecad/`
(`Init.py`, `InitGui.py` and `package.xml` come in phase 4):

- `sketch_data.py`: `snapshot(sketch)` reads a `SketchObject` into plain data (geometry,
  external geometry, constraints, expressions, the document's VarSets, the sketch's solver
  status). None of the modules import FreeCAD, so the mapping is tested without it.
- `export_sketch.py`: `to_document(data)` (the mapping, §4) and `export_sketch(sketch, path)`.
  Unsupported features are collected and raised together as a `CpskExportError` (R4); the
  document is compiled by `cpsk_core` before it is returned, so a mapping gap cannot write a
  broken file. Constraints are placed with `cpsk_core.nest_constraints` (spec §11.4, new in
  `cpsk_core.canonical`).
- `expressions.py`: FreeCAD expression → CPSK formula, with FreeCAD's precedence (§4.3).

Details settled while building it:

- Variables: every user property of each VarSet that an expression references (directly or
  through another variable) is exported, in the VarSet's property order, so unused variables
  survive a round trip. Two referenced VarSets with the same property name, a variable named
  like a constraint, or another property type than length, distance, angle, float or integer
  are refused.
- D6 is implemented for deactivated constraints: they are written, with full operands, inside a
  `<freecad:inactive>` element (namespace `https://github.com/shevron/plotzker/ns/cpsk-freecad`)
  in `<constraints>`, which CPSK readers skip. Label positions are not exported yet (phase 3,
  with D4).
- D4 (keeping ids from an earlier import) came in phase 3, below.
- The sketch's label becomes the metadata `<title>`.
- Angle constraint values are written to 12 significant digits (FreeCAD stores radians, so
  30° reads back as 29.999999999999996°); lengths and stored coordinates are written exactly.
- Tests (`cadder/tests/test_cpsk_freecad.py`): the 39 phase 0 cases plus export cases
  (`cadder/tests/cpsk_freecad/export_cases.py`: VarSet expressions with both precedence
  differences, external geometry, a deactivated constraint, refusals) map without FreeCAD; with
  FreeCAD each is built, solved, exported, and `cadder.cpsk` must solve the file to FreeCAD's
  geometry within 1e-9 mm with 0 degrees of freedom.
- Found for phase 3: FreeCAD reads some identifiers as units in expressions (a constraint named
  `h`, hours, cannot be referenced: "Failed to parse expression"). CPSK ids that are FreeCAD unit
  names need a decision on import.

**As built (phase 3):** `import_sketch.py`: `from_document(document)` maps a CPSK document to
the same plain data the exporter reads (so both directions are tested without FreeCAD), and
`import_sketch(doc, path)` creates the sketch and its VarSet.

- Constraints are added in one batch (FreeCAD solves only on recompute), then made non-driving,
  deactivated (from `<freecad:inactive>`) and given their expressions, so stored coordinates are
  not disturbed by intermediate solves. Non-driving constraints take their written value.
- D4: a hidden `CpskData` string property on the sketch holds JSON with the primitive ids (keyed
  by FreeCAD's GeometryId, which survives deleting and adding geometry; `""` for primitives
  without an id), D9 renames, the generated names of anonymous constraints that carry a formula
  (`cpsk_1`, …: FreeCAD needs a name for an expression), variable limits and order (FreeCAD
  lists VarSet properties alphabetically), the metadata and the VarSet's name. Export uses it:
  kept ids (generated ones avoid them), names, limits, variable order and metadata (`title`
  follows the sketch label); ids of primitives that had none are dropped again when nothing
  references them.
- VarSet: one per imported sketch, `<Sketch>Variables`, labelled "`<title>` variables"; variable
  expressions use bare property names, sketch expressions `<VarSet>.<name>` and
  `Constraints.<name>`. A variable that uses a constraint value while constraints use
  variables is refused: FreeCAD marks the circular VarSet–sketch dependency invalid.
- Expressions are written with FreeCAD's precedence and syntax (`-2^2` → `-(2 ^ 2)`,
  `2^3^2` → `2 ^ (3 ^ 2)`, `deg` → `°`, `;` between arguments). FreeCAD rewrites expression
  text (`,` → `;`, `1e1` → `10`); the exporter accepts its forms.
- Export now writes arc angles with the start in [−180°, 180°) and the end at start + sweep:
  FreeCAD keeps angles in [0°, 360°), and this keeps both round trips stable.
- External geometry from a FreeCAD export comes back as ordinary blocked construction geometry
  (the link to the other object is not part of CPSK); the re-export is the same file.
- Comments and extension content other than FreeCAD's are not kept in FreeCAD.
- Tests: every FreeCAD case exported, imported into FreeCAD and exported again gives the same
  file (R5); the spec example and `cadder/tests/cpsk_freecad/import/units-as-names.cpsk` (D9,
  an anonymous primitive, precedence, a deactivated constraint) import fully constrained and
  export to the same file without its comments (D4).

**As built (phase 4):**

- `Init.py` registers "CPSK sketch (*.cpsk)" with `FreeCAD.addImportType` and `addExportType`;
  `importCPSK.py` has FreeCAD's importer functions `open`, `insert` and `export`. Warnings go to
  the Report view; a refused import or export (and an export without exactly one sketch
  selected) also shows a dialog listing every problem. Without the GUI, errors are raised.
  There is no `InitGui.py`: File menu types need none.
- `package.xml` declares the addon as a `<workbench>` item although it has no workbench:
  FreeCAD 1.1 runs `Init.py` only for workbench items when `package.xml` is present (an
  `<other>` item is never loaded). Its licence is TBD, as the RFC's.
- `make freecad-addon` links `cadder/freecad-addon/CPSK` into FreeCAD's user `Mod` folder
  (`FREECAD_MOD`, default `~/Library/Application Support/FreeCAD/v1-1/Mod`; it refuses to replace
  anything there that is not a link). `cpsk_freecad` then finds `cpsk_core` in the repository's
  `cadder/src` (through the link's real path); a released addon would ship a copy instead.
- Found while testing: FreeCAD checks units in sums. In a mm/deg document a unitless number
  added to a length or angle means mm or degrees, so the import writes it with its unit
  (`s - 6` → `Constraints.s - 6 mm`, a unitless subexpression gets `* 1 mm`); `min`, `max` and
  `abs` likewise. Without this FreeCAD rejected the expression and kept the old value. The
  import now reports such FreeCAD errors as warnings, and the tests require none. To keep
  CPSK → FreeCAD → CPSK unchanged, `CpskData` keeps each formula as written with FreeCAD's
  stored expression; export writes the original while the expression is unchanged.
- Tests: the entry points run in `freecadcmd` (`run_entry_points.py`). Checked once by hand in
  FreeCAD 1.1.3's GUI on macOS: the File menu's path (module looked up by extension; `insert`,
  `open`, `export`) imports the spec example fully constrained and exports it unchanged.
  FreeCAD's Python `FreeCADGui.insert`/`open` only handle built-in formats, so they cannot be
  used to test this.

## 4. Mapping

### 4.1 Geometry

| FreeCAD | CPSK | Notes |
|---|---|---|
| `Part.Point` | `point` | |
| `Part.LineSegment` | `line` | |
| `Part.Circle` | `circle` | |
| `Part.ArcOfCircle` | `arc` | FreeCAD arcs are counterclockwise, as in CPSK; angles converted from radians to the document angle unit |
| Construction flag (`getConstruction`) | `construction="true"` | |
| External geometry (GeoId ≤ -3) | Construction primitive with a nested `<block/>` | R2: fixed in FreeCAD, so fixed in CPSK; constraints on it are remapped to the new primitive |
| Ellipse, arc of ellipse, hyperbola, parabola, B-spline | — | Unsupported (R1, R4) |

Primitive ids: CPSK constraints reference primitives by id, FreeCAD by index. Export generates
`edge1`, `edge2`, … from the GeoId (FreeCAD's own `Edge<n>` naming) and `point<n>` for points,
unless an id was kept from an earlier import (decision D4).

### 4.2 Constraints

*P*: (GeoId, PosId 1–3); *E*: (GeoId, PosId 0). All other combinations are unsupported.

| FreeCAD type and operands | CPSK |
|---|---|
| `Coincident` (P, P) | `coincident a b` |
| `PointOnObject` (P, E: line, circle, arc, axis) | `point-on point object` |
| `Horizontal` / `Vertical` (E: line) | `horizontal` / `vertical` with `of` |
| `Horizontal` / `Vertical` (P, P) | `horizontal` / `vertical` with `a`, `b` |
| `Parallel`, `Perpendicular` (E: line, E: line) | `parallel`, `perpendicular` |
| `Tangent` (E, E) | `tangent` (curves) |
| `Tangent` (P end point, P end point) | `tangent` (end points) |
| `Equal` (two lines, or circles/arcs) | `equal` |
| `Symmetric` (P, P, E: line) / (P, P, P) | `symmetric` with `about` |
| `Block` (E) | `block` |
| `Distance` (E: line) | `distance of` |
| `Distance` (P, P) / (P, E: line) | `distance a b` |
| `DistanceX` / `DistanceY` (E: line) | `distance-x a=<l>.start b=<l>.end` |
| `DistanceX` / `DistanceY` (P) | `distance-x a=origin b=<p>` |
| `DistanceX` / `DistanceY` (P, P) | `distance-x a b` |
| `Radius`, `Diameter` (E: circle, arc) | `radius`, `diameter` |
| `Angle` (E: line) | `angle a=x_axis b=<l>` |
| `Angle` (E: arc) | `angle of` (sweep) |
| `Angle` (E: line, E: line) | `angle a b` |
| `Driving = False` | `driving="false"` |
| `Name` | `id` (decision D5 for names that are not valid identifiers) |
| `IsActive = False` | Decision D6 |
| `Tangent` / `Perpendicular` via a point (P, E) or (E, E, P), `Angle` via a point or with PosIds, `Distance` with circles or arcs (FreeCAD 1.x), arc length, `InternalAlignment`, `SnellsLaw`, `Weight` | Unsupported in 0.1 (spec Appendix A, A12) |

Phase 0 verified every row: FreeCAD 1.1.3 and `cadder.cpsk` solve all 39 test cases to the same
geometry, and the signs and directions match spec §9.3 ([results](freecad-conventions.md)).

### 4.3 Expressions

| FreeCAD | CPSK | Notes |
|---|---|---|
| `2 * 5 mm`, `30 °`, `30 deg` | `2 * 5mm`, `30deg` | Units: `mm`, `cm`, `m`, `in`, `°`/`deg`, `rad` |
| Unitless numbers: mm and degrees | Unitless numbers: the document units | Direct translation for `mm`/`deg` documents only (D8) |
| `-2^2` = 4, `2^3^2` = 64 (unary minus binds tighter than `^`; `^` is left-associative) | `-2^2` = −4, `2^3^2` = 512 | Translation adds parentheses in both directions (spec A14) |
| `Constraints.w` | `w` | Driving constraint values only (spec §10.5) |
| `<VarSet>.width` | `width` | D2 |
| `+ - * / ^`, `abs sqrt min max sin cos tan asin acos atan atan2`, `pi` | same | Unitless trigonometric arguments and results are degrees in FreeCAD, as in CPSK documents with `unit-angle="deg"` |
| Reference to a non-driving constraint of the same sketch | — | Refused by FreeCAD too ("Reference constraint from this sketch cannot be used"), as spec §10.5 does |
| Other functions, conditionals (`? :`), spreadsheet or other-object references, units such as `mm^2` | — | Unsupported (R3) |

FreeCAD expressions carry units, CPSK 0.1 formulas don't (spec A6). Phase 0 found FreeCAD
lenient here: a length × length value was accepted for a length constraint.

VarSet property types: `length` variables become `App::PropertyDistance` (signed;
`App::PropertyLength` rejects negative values), `angle` → `App::PropertyAngle`,
`number` → `App::PropertyFloat`.

## 5. Decisions

D1–D7 were accepted on 2026-11-23; D8 (from phase 0) and D9 (from phase 3) were accepted the same day.

| # | Question | Options | Decision |
|---|---|---|---|
| D1 | How does the addon get the CPSK reader and writer? | (a) Re-implement in the addon. (b) Extract a pure-standard-library core package (`cpsk_core`, Python ≥ 3.11) used by both cadder and the addon. (c) The addon runs cadder's Python in a subprocess. | **(b)**: one implementation, no duplicate parser. The RFC already expects the library to become its own package (§7.1). The cost is giving up 3.12+ syntax in the core (`type` aliases, unquoted forward references) |
| D2 | Where do CPSK variables live in FreeCAD? | (a) A `VarSet` per imported sketch. (b) A Spreadsheet. (c) Dynamic properties on the sketch. | **(a)**: typed properties with units and expression support, designed for this in FreeCAD 1.x. Export reads variables from VarSets that the sketch's expressions reference |
| D3 | Where does the addon live? | (a) In this repository (`cadder/freecad-addon/`), installed with a `make` target that links it into FreeCAD's `Mod` folder. (b) Its own repository from the start. | **(a)** while the format is a draft; move it with cadder later |
| D4 | CPSK → FreeCAD → CPSK: keep primitive ids, metadata and variable limits? | (a) Not kept; export generates ids. (b) Kept in hidden properties on the sketch and VarSet. | **(b)**: makes the reverse round trip stable too (unchanged files re-export unchanged), at little cost |
| D5 | FreeCAD constraint names that are not valid CPSK identifiers (spaces, reserved words) | (a) Refuse export and list them. (b) Rename them (e.g. spaces to `_`) and warn. | **(a)**: renaming would break R5 and expressions that reference the name |
| D6 | Deactivated constraints (`IsActive = False`), label positions and similar FreeCAD-only state | (a) Unsupported: refuse. (b) Dropped with a warning. (c) Kept in a FreeCAD extension namespace (spec §11.3, RFC §8 TBD). | **(c)**: this is what the extension namespace is for, and it keeps R5 |
| D7 | Expressions FreeCAD can't convert (spreadsheet references, conditionals) | (a) Refuse (R3, R4). (b) Optionally freeze them as literal values. | **(a)**, with (b) as an explicit option later if needed |
| D9 | CPSK ids that FreeCAD's expressions read as units or constants (`t`, `h`, `s`, `g`, `e`, `l`, `m`, `min`, `in`, capital letters such as `N` or `T`, …): FreeCAD cannot give such a constraint or variable an expression or reference it | (a) Rename on import (`t` → `t_`) with a warning, and keep the original id so export writes it back. (b) Refuse the import and list them. (c) Import the value without the expression. | **(a)**: files stay importable (`t` for a thickness is common) and round trips stay lossless. Only ids that carry a formula or are referenced are renamed; FreeCAD itself decides what is a unit (`App.Units.Quantity`) |
| D8 | Import of documents whose units are not mm and degrees (FreeCAD reads unitless numbers as mm and degrees) | (a) Refuse them in the first version; export always writes mm and degrees. (b) Convert: variables become unitless VarSet floats in document units, and each constraint expression is rewritten to work in document units (`(<formula>) * 1 cm`, constraint references divided by `1 cm`, trigonometric arguments multiplied by `1 rad`). | **(a)** now, (b) when a non-mm document is needed |

## 6. User interface

- **File > Export:** with one sketch selected, "CPSK sketch (*.cpsk)" writes it. Unsupported
  features abort the export with a dialog that lists each one (constraint name or number, type,
  reason). Solver problems (conflicting, redundant constraints, remaining degrees of freedom) are
  shown as warnings; the file is still written.
- **File > Import / Open:** a `.cpsk` file becomes a new sketch (and its VarSet, D2) in the active
  document. Load errors are shown with their line numbers; after import, FreeCAD's own solver
  messages apply.
- **Headless API:** `cpsk_freecad.export_sketch(sketch, path)` and
  `cpsk_freecad.import_sketch(doc, path)`, usable from `freecadcmd` and from tests.

## 7. Phases

| Phase | Work | Done when |
|---|---|---|
| **0. Conventions spike** ✅ | Script in `freecadcmd`: build one sketch per constraint row in §4.2 and compare FreeCAD's solved geometry with `cadder.cpsk` solving the same constraints. Check expression units, trigonometric units, VarSet references and the tangent `Value`. | Every §4.2 row verified or marked unsupported; spec §9.3 TBD resolved |
| **1. Core package** ✅ | Extract `cpsk_core` (D1): Python 3.11 syntax, lossless `Document` model, canonical writer; `cadder.cpsk` builds on it. | cadder tests pass; the core's tests pass under FreeCAD's Python (`make test-cpsk-core`); reading and writing the spec example gives the same file |
| **2. Export** ✅ | `export_sketch` (§4), unsupported-feature report, expressions, external geometry. | A test corpus of FreeCAD sketches exports; `cadder.cpsk` solves each export to FreeCAD's geometry (within 1e-9 mm); unsupported features are refused with a list |
| **3. Import** ✅ | `import_sketch`, VarSet creation (D2), id preservation (D4). | FreeCAD → CPSK → FreeCAD gives the same geometry, constraints, names and expressions (R5); the spec example imports fully constrained |
| **4. GUI and install** ✅ | Import/export registration, dialogs, `make freecad-addon` (link into `Mod`), `package.xml`. | Import and export work from the File menu in FreeCAD 1.1 on macOS |
| **5. Docs** | Addon README, cadder docs, spec updates from phase 0, STATUS tasks. | Docs describe install and use; open spec issues updated |

## 8. Testing

- Plugin tests run FreeCAD headless (`freecadcmd`), like `cadder/tests/test_freecad.py`, and are
  skipped when FreeCAD is not installed.
- **Corpus:** one small sketch per §4.2 row, the spec example, the slot from `test_cpsk.py`, a
  sketch with external geometry, and one per unsupported feature (expected refusal).
- **Round trips:** FreeCAD → CPSK → FreeCAD (R5: geometry, constraints, names, expressions,
  driving flags); CPSK → FreeCAD → CPSK (D4: the same canonical file).
- **Cross-solver check:** for each exported file, `cadder.cpsk` (PlaneGCS through `planegcs`) and
  FreeCAD (PlaneGCS inside Sketcher) must agree on the solved geometry.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Sign and direction conventions differ between FreeCAD's constraint operands and the spec | Phase 0, before any mapping code |
| FreeCAD's unit-aware expressions differ from unitless CPSK formulas | Phase 0: lenient in practice (§4.3); import reports any expression FreeCAD rejects; revisit with spec A6 |
| CPSK ids that FreeCAD reads as units (`h`, `s`, …) cannot be referenced in FreeCAD expressions | D9: renamed on import, restored on export |
| FreeCAD internals change between releases (constraint fields, VarSet API) | Only public Python API; pin the tested FreeCAD version in `package.xml`; the cross-solver tests catch drift |
| Two Python versions to support (3.11 core, 3.14 cadder) | Core tested under both; ruff `target-version = "py311"` for the core |
