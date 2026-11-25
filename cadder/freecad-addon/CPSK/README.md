# CPSK addon for FreeCAD

Opens, imports and exports FreeCAD Sketcher sketches as CPSK files (`.cpsk`), the
constraint-based parametric sketch format of cadder ([spec 0.1](../../docs/cpsk/spec-0.1.md),
draft). Draw and edit a sketch in FreeCAD, export it, and load it in cadder with
`load_sketch("part.cpsk", params={...})`; or import a hand-written `.cpsk` file into FreeCAD to
check it visually.

Requires FreeCAD 1.1 (tested with 1.1.3 on macOS). Design and decisions D1–D9:
[plugin plan](../../docs/cpsk/freecad-plugin-plan.md).

## Install

From the workspace root:

```bash
make freecad-addon
```

This links this folder into FreeCAD's user `Mod` folder as `CPSK` (default
`~/Library/Application Support/FreeCAD/v1-1/Mod`; set `FREECAD_MOD=...` for another one).
Restart FreeCAD. The addon uses `cpsk_core` from the repository (`cadder/src`), so keep the
repository where it is; changes to the code take effect at the next FreeCAD start. To remove it,
delete the `CPSK` link from the `Mod` folder.

There is no Addon Manager release yet: a release would ship its own copy of `cpsk_core`.

License: LGPL-3.0-or-later, as the rest of cadder ([`LICENSE`](../../LICENSE)).

## Use

- **File > Open** a `.cpsk` file: a new document with the sketch and its variables.
- **File > Import** a `.cpsk` file: the sketch is added to the active document.
- **File > Export**, with one sketch selected, file type "CPSK sketch (*.cpsk)".

Warnings appear in the Report view (View > Panels > Report view). If an import or export is
refused, a dialog lists every problem; nothing is created or written.

The sketch's label becomes the document `<title>` and back. Variables live in a VarSet named
`<Sketch>Variables`, labelled "`<title>` variables": edit them there (or in the expressions of
constraints) and export again.

### From Python

```python
import FreeCAD as App
from cpsk_freecad import export_sketch, import_sketch

sketch, warnings = import_sketch(App.ActiveDocument, "plate.cpsk")
warnings = export_sketch(sketch, "plate-out.cpsk")  # raises cpsk_core.CpskExportError if refused
```

Both return lists of `cpsk_core.Diagnostic`. `from_document` and `to_document` do the same
mapping on plain data, without FreeCAD (`cpsk_freecad.sketch_data`).

## What is supported

| FreeCAD | CPSK |
|---|---|
| Points, line segments, circles, arcs of circles; construction geometry | `point`, `line`, `circle`, `arc`; `construction="true"` |
| External geometry | Blocked construction geometry (`external1`, …); imported back as ordinary geometry |
| Coincident, point on object, horizontal, vertical, parallel, perpendicular (two lines; a line and a circle or arc; end points of a line and an arc), tangent (curves, end points), equal, symmetric, block, lock | The constraints of spec §9.3 |
| Distance, DistanceX/Y, radius, diameter, angle (line, arc sweep, two lines); reference (non-driving) dimensions | Dimensional constraints, `driving="false"` |
| Constraint names | Constraint ids |
| Expressions with `+ - * / ^`, `abs sqrt min max sin cos tan asin acos atan atan2`, `pi`, units `mm cm m in ° deg rad`, references to the sketch's constraints and to VarSet properties | Formulas and variables |
| Deactivated constraints | Kept in `<freecad:inactive>` (namespace `https://github.com/shevron/plotzker/ns/cpsk-freecad`), ignored by CPSK readers |

Export refuses, and lists, anything else: ellipses, B-splines and other curves; other constraint
forms (tangent or perpendicular via a point, perpendicular between two curves, distances to circles, angles at end points, arc
length, Snell's law, internal alignment, …); constraint names that are not CPSK identifiers or
are reserved words; expressions with other functions, conditionals, spreadsheet or other
objects' references, or other units.

Import refuses documents whose units are not millimetres and degrees (plan D8), and a variable
that uses a constraint value while constraints use variables (FreeCAD rejects that circular
dependency between the VarSet and the sketch).

Sketch problems FreeCAD reports when exporting (remaining degrees of freedom, conflicting,
redundant or malformed constraints) are warnings; the file is still written.

## Round trips

- **FreeCAD → CPSK → FreeCAD** gives the same geometry, constraints, names, expressions,
  driving flags and deactivated constraints; exporting again writes the same file.
- **CPSK → FreeCAD → CPSK** writes the same file, except for comments and extension content
  other than the addon's own. The sketch keeps what FreeCAD has no place for in a hidden
  `CpskData` property: primitive ids (also for primitives without one), metadata, variable
  limits and order, and each formula as written (exported as written while its FreeCAD
  expression is unchanged).

Things that change on the way:

- **Names FreeCAD reads as units** (`t`, `h`, `s`, `g`, `l`, `e`, `m`, `min`, …, and capitals
  such as `N` or `T`) cannot carry or be used in a FreeCAD expression. On import such an id is
  renamed (`t` → `t_`) with a warning, and export writes `t` again (D9).
- **Anonymous constraints with a formula** get a name (`cpsk_1`, …), because FreeCAD expressions
  need one; export writes them without an id again.
- **Expressions** are written in FreeCAD's syntax: `^` precedence differs (CPSK `-2^2` is
  FreeCAD `-(2 ^ 2)`), units are separated (`2.5cm` → `2.5 cm`, `30deg` → `30 °`), and FreeCAD
  checks units in sums, so a unitless number added to a length or angle gets its unit
  (`s - 6` → `Constraints.s - 6 mm`).
- **Arc angles** are written with the start in [−180°, 180°).

## Files

| File | Purpose |
|---|---|
| `Init.py` | Registers the file type with FreeCAD |
| `importCPSK.py` | File > Open, Import and Export |
| `package.xml` | Addon metadata (declared as a workbench item: FreeCAD runs `Init.py` only for those) |
| `cpsk_freecad/sketch_data.py` | Plain-data snapshot of a sketch; the data kept for round trips |
| `cpsk_freecad/export_sketch.py` | FreeCAD → CPSK |
| `cpsk_freecad/import_sketch.py` | CPSK → FreeCAD |
| `cpsk_freecad/expressions.py` | FreeCAD expressions ↔ CPSK formulas |

## Tests

`cadder/tests/test_cpsk_freecad.py`, run by `make test`. Without FreeCAD: the mapping and both
round trips on plain data. With FreeCAD (`freecadcmd`; skipped when it is not installed): every
case in `cadder/tests/cpsk_freecad/` is built in FreeCAD, exported, solved by `cadder.cpsk` to
FreeCAD's geometry (within 1e-9 mm), imported back and exported again; the spec example and
`import/units-as-names.cpsk` import fully constrained; the File menu entry points run headless.
