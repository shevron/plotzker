# RFC: CPSK, a constraint-based parametric 2D sketch format

| | |
|---|---|
| **Status** | Draft |
| **Format version** | 0.1 |
| **Created** | 2026-11-23 |
| **Related** | [`../sketch-formats.md`](../sketch-formats.md) (prior research, plotzker D23/D24) |
| **Specification** | [`../cpsk/spec-0.1.md`](../cpsk/spec-0.1.md) (draft) |
| **Implementation** | Reader: `cadder.cpsk`. FreeCAD plugin: [plan](../cpsk/freecad-plugin-plan.md), [addon](../../freecad-addon/CPSK/README.md) |

## Abstract

This document specifies the requirements and initial design of CPSK, an open, XML-based file
format for constraint-based parametric 2D sketches. A CPSK file holds geometry, constraints,
named variables and formulas. A solver turns it into fixed geometry that can be exported to
SVG and used by code-driven CAD tools (cadder, PythonSCAD, OpenSCAD). A FreeCAD plugin
provides visual editing through the Sketcher workbench.

## Conventions

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT" and "MAY" are to be interpreted as
described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

Items marked **TBD** are pending further research and experimentation.

## 1. Motivation

In a code-driven CAD project most geometry is defined in code. Some geometry is easier to
define as a 2D sketch that is then extruded or pocketed into a solid. Two kinds of designer
benefit:

- **Human designers** familiar with parametric CAD use constraint-based sketches routinely,
  and find it easier to edit a profile visually than in code.
- **AI designers** can write a sketch in a small declarative vocabulary as easily as code. A
  smaller vocabulary is expected to produce fewer errors.

Standard hardware is a typical case. The profile of a 2020 V-slot aluminium extrusion is well
known and simple to draw as a sketch; modelling it procedurally is laborious, and corrections
are easier to make visually.

cadder currently loads sketches as plain SVG (`cadder.geometry.load_sketch`). SVG carries
geometry only: dimensions are not named, there are no constraints, and changing a dimension
means redrawing the profile.

A format that visual sketchers (e.g. FreeCAD Sketcher) can create and edit, and that
code-driven CAD tools can consume, would connect visual and code-driven workflows, and let
human and AI designers work on the same sketches.

## 2. Prior art

No open, documented format for parametric 2D sketches is known to meet the requirements in
§3. [`../sketch-formats.md`](../sketch-formats.md) has the full survey; in short:

| Format | Limitation |
|---|---|
| SVG | Geometry only, no constraints or parameters. Includes much that is not needed (styling, colours, fills, strokes, text, transforms). |
| DXF | Geometry only, no constraints or parameters. Less widely supported than SVG. |
| STEP (ISO 10303-108) | Defines parametric and constraint data, but CAD tools do not implement it in practice. |
| FreeCAD sketch | No standalone format. Sketches are stored in `Document.xml` inside an `.FCStd` (ZIP) project file; the schema is internal and changes between releases. |
| SolveSpace `.slvs` | Text records defined by the implementation, not formally documented. |
| Proprietary (Fusion, Onshape, SolidWorks) | Closed; not usable by cadder. |

### 2.1 Relation to earlier decisions

plotzker decision D24 kept plain SVG after rejecting two alternatives (see
[`../sketch-formats.md`](../sketch-formats.md)):

- **Option B** (sketches written in a Python DSL on a solver): rejected because it gives no
  visual editing and little over plain PythonSCAD.
- **Option C** (SVG with constraint metadata): rejected because it requires inventing a
  format *and* lacks an editor.

This proposal revisits option C with two differences. CPSK is a separate XML format, not
annotated SVG (§3.2). The missing editor is provided by a FreeCAD import/export plugin (§8).

## 3. Goals and non-goals

### 3.1 Goals

The format:

- **G1.** MUST be able to represent a constraint-based sketch equivalent to a FreeCAD
  Sketcher sketch, within the feature set defined in §5.
- **G2.** MUST be convertible to standard vector formats (SVG, and possibly DXF) without loss
  of geometric accuracy. Parametric data (constraints, variables, formulas) is dropped by the
  conversion.
- **G3.** MUST be open, documented and implementable by third-party software.
- **G4.** SHOULD reuse existing standards and conventions (XML, SVG nomenclature) where
  possible.

### 3.2 Non-goals

- A general-purpose CAD application or a graphical editor of our own. Visual editing is
  delegated to existing tools (FreeCAD).
- Presentation data: styles, colours, fills, strokes, text, transforms.
- 3D geometry and sketch placement in 3D space.
- Profiles and validity. The format does not define faces, holes or closed profiles, and does
  not require geometry to be valid or constraints to be solvable (§5.3).
- SVG compatibility. A CPSK document is not a valid SVG document and MUST NOT be designed to
  be one. Editing it with an SVG editor would risk losing CPSK data and adding incompatible
  SVG data.

## 4. Proposed approach

The first working version (MVP) consists of three deliverables:

1. **Format specification.** A declarative XML format for parametric 2D sketches. It borrows
   geometric nomenclature from SVG but is neither a subset nor a superset of it: SVG features
   outside the scope of §3 are omitted and parametric features are added. §5 lists the
   required content and §6 the syntax.
2. **Python reference library** (§7). Parses and solves CPSK documents, and exports the
   solved geometry as SVG. Through SVG it works with PythonSCAD and OpenSCAD, and therefore
   with cadder.
3. **FreeCAD plugin** (§8). Imports and exports CPSK documents as Sketcher sketches, providing
   visual editing and interoperability with FreeCAD.

This is expected to be the shortest path to a usable format.

## 5. Format requirements

### 5.1 Metadata

Optional descriptive data: author, timestamps, free-form tags.

### 5.2 Units

A document declares one length unit and one angle unit. Unitless lengths and angles anywhere
in the document are in these units.

| Unit | Default | Allowed values |
|---|---|---|
| Length | `mm` | `mm`, `cm`, `m`, `in` (TBD: full list) |
| Angle | `deg` | `deg`, `rad` |

A length or angle value MAY carry an explicit unit (e.g. `5cm`, `2in`, `0.5rad`). A reader
MUST convert such a value to the document unit before use.

### 5.3 Validity

A CPSK document is not required to describe valid or solvable geometry. A document MAY
contain:

- open wires and other geometry that does not form closed profiles;
- under-constrained, over-constrained or conflicting constraints;
- stored coordinates (§5.6) that do not satisfy the constraints.

Validation is the responsibility of the solver and the consumer, according to the needs of
the application. For example, cadder requires closed loops for extrusion and derives faces and
holes with an even-odd rule, as `load_sketch` does for SVG today.

### 5.4 Variables

Named variables used by constraints and formulas. A variable:

- MUST have a type: `number` (the default, dimensionless), `length` or `angle`.
- MUST have a default value. A `length` or `angle` value MAY carry a unit (§5.2).
- MAY have limits (minimum and maximum).
- MAY be overridden by the caller at solve time; the solver MUST reject an override outside
  the variable's limits.

TBD: type rules for formulas, e.g. whether a `number` may be assigned to a `length` and what
type `length * length` or `length / length` has.

### 5.5 Coordinate system

The sketch plane uses a right-handed coordinate system with the y axis pointing up (unlike
SVG) and the origin at (0, 0). A document has no global transform: origin, orientation and
scale are not stored.

### 5.6 Geometry

Geometric primitives, equivalent to the FreeCAD Sketcher primitives:

- Points, line segments, circles and circular arcs.
- B-splines MAY be added in a later version.

Polylines, polygons, rectangles and similar are drawing shortcuts, not primitives: they MUST
be stored as their constituent primitives (e.g. a polygon as connected line segments joined by
coincidence constraints).

Every primitive MUST store its coordinates. The stored coordinates are the solver's initial
values and the last solved state. A numerical solver needs a starting point close to the
intended solution: with unsigned constraints (e.g. angles) it can converge to a mirrored
solution from a poor one. Stored coordinates also let a reader without a solver render the
sketch.

Any primitive MAY be marked as **construction geometry**: it takes part in solving but is not
exported or rendered.

### 5.7 Constraints

Constraints equivalent to the FreeCAD Sketcher set, including: coincident, horizontal,
vertical, parallel, perpendicular, tangent, equal, point-on-object, symmetric, distance
(length), angle, radius and diameter. Each constraint type applies to specific primitive
types.

Constraint semantics SHOULD follow FreeCAD Sketcher, whose solver (PlaneGCS) is the
solver used by the reference library (§7.3).

### 5.8 Measured values

A dimensional constraint (distance, angle, radius, diameter) MAY be marked as non-driving: it
does not constrain the geometry, but measures the solved value, which formulas can then read.

FreeCAD calls these *reference constraints* (toggled between driving and reference) and
SolveSpace *reference dimensions*; other CAD tools use *driven dimension*. "Constraint" is
misleading, since the element constrains nothing, and the concept applies only to dimensional
constraints.

**TBD:**

- Name, e.g. *measurement* or *driven dimension*, and whether it is a separate element or a
  flag on a constraint.
- Semantics, after reviewing FreeCAD and SolveSpace behaviour. PlaneGCS supports
  non-driving constraints directly (`driving=False` in `planegcs`), and excludes them from the
  degrees of freedom count. In particular: a driving value
  whose formula depends on a measured value is a dependency on the solver result. It is either
  a cycle (an error) or requires iterative solving.

### 5.9 Identifiers and references

Primitives, constraints and variables MAY have an identifier. An identifier MUST be unique
within the document.

Each primitive type implicitly defines named points and properties, which constraints and
formulas reference as `<id>.<name>` (e.g. `l1.start`, `a1.center`, `c1.radius`). Proposed set,
open to revision:

| Primitive | Points | Properties |
|---|---|---|
| Point | (the point itself, `<id>`) | `x`, `y` |
| Line | `start`, `end`, `mid` | `length`, `angle` |
| Circle | `center` | `radius`, `diameter` |
| Arc | `start`, `end`, `center`, `mid` | `radius`, `diameter`, `start_angle`, `end_angle`, `sweep` |

A point reference (e.g. `l1.start`) also has the properties `x` and `y` (e.g. `l1.start.x`).

### 5.10 Values and formulas

A constraint or variable value is one of:

- a literal, optionally with a unit (§5.2);
- a reference to a variable or to an element property (§5.9);
- a formula, evaluated at solve time.

Evaluation order is implicit, derived from the references between values. A reader MUST
detect circular references and report them as errors.

The formula syntax is deliberately small, close to the SolveSpace and FreeCAD expression
syntaxes:

- Literals with optional units: `5`, `2.5mm`, `30deg`.
- Operators: `+`, `-` (binary and unary), `*`, `/`, `^`, parentheses.
- Functions: `abs`, `sqrt`, `min`, `max`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`,
  `atan2`.
- Constants: `pi`.

**TBD:** the exact grammar (precedence, whitespace between number and unit, identifier
characters), the final function list, and the angle convention of trigonometric functions
(argument and result in the document angle unit, or always radians).

## 6. Naming and syntax

### 6.1 Name

- **Name:** CPSK (Constraint-based Parametric SKetch).
- **File extension:** `.cpsk`.

No existing file format is known to use the `.cpsk` extension (checked 2026-11-23). The
acronym is used elsewhere, but not for file formats. The PyPI name `cpsk` is taken by an
unrelated package. This matters only if the reference library is published on its own (§7.1).

### 6.2 Syntax

CPSK documents are XML. Documents can be written, parsed and validated with standard XML
tools. An XML Schema (XSD) SHOULD be published for validation.

Rationale: XML is more verbose than JSON, TOML or YAML, but has these advantages:

- mature tooling: parsers, schema validation, namespaces;
- resemblance to SVG, whose geometric nomenclature CPSK borrows;
- a typed, hierarchical document model, better suited to a declarative language than JSON
  and TOML, which are designed for data serialisation and configuration.

YAML MAY be evaluated through experimentation, but XML is the expected choice.

TBD: element and attribute names, and an annotated example document (e.g. a constrained
rectangle with a hole).

### 6.3 Versioning and extensions

- Each document SHOULD declare the format version and the CPSK XML namespace URI.
- A reader that encounters an unknown element or attribute MUST NOT silently ignore it: it
  MUST at least issue a warning, and MAY reject the document.
- Data outside the CPSK namespace MAY be used for tool-specific information (e.g. FreeCAD
  data, §8). TBD: whether foreign namespaces count as "unknown" for the rule above.

## 7. Reference library

### 7.1 Packaging and interface

- The reference library is a subpackage of cadder (proposed name: `cadder.cpsk`). It may be
  split into a separate package later.
- The first deliverable is a low-level Python API: load, override variables, solve, inspect
  diagnostics, export SVG. A command-line tool taking arguments or a configuration file MAY
  be built on top of it later (§10).

### 7.2 Errors and warnings

The library reports problems at two stages.

| Stage | Errors (processing stops) | Warnings (processing continues) |
|---|---|---|
| **Load** (syntax and references) | Malformed XML or schema violation; reference to a missing identifier or variable; circular reference (§5.10); invalid unit; variable override outside its limits | Unknown element or attribute (§6.3) |
| **Solve** (solver-specific) | Conflicting constraints; failure to converge | Remaining degrees of freedom (under-constrained sketch); redundant constraints |

A sketch with warnings MUST still be usable: it can be solved, imported, exported and
rendered. The library MUST report warnings in a structured form (type, affected identifiers,
degrees of freedom) so that callers can apply stricter rules. For example, cadder MAY offer a
strict mode that fails on any solve warning.

### 7.3 Solver

The reference library uses FreeCAD's PlaneGCS, through the
[`planegcs`](https://github.com/spookylukey/planegcs) Python package. It runs without
FreeCAD, so it can be a normal dependency of any project's virtual environment.

| | `planegcs` (PlaneGCS) | `python-solvespace` / `py-slvs` (SolveSpace) |
|---|---|---|
| Licence | LGPL-2.1-or-later (preferred) | GPL-3 |
| Semantics | Identical to FreeCAD Sketcher, which simplifies the plugin | Close, but not identical (e.g. signed distances) |
| Non-driving constraints | Yes (`driving=False`) | Yes (reference dimensions) |
| Diagnostics | Degrees of freedom, conflicting, redundant and partially redundant constraints | Degrees of freedom, failed constraints by index |
| Determinism | Bit-identical results between runs (fixed in the wrapper; FreeCAD itself is not deterministic) | Not checked |
| Python 3.14 | Wheels for Linux and Windows (3.12–3.14); **no macOS wheels**: builds from source with a C++ toolchain, Eigen 3 and Boost headers | `python-solvespace` built from source here; `py-slvs` wheels only up to 3.13 |

Status: verified 2026-11-23 on macOS (arm64, Python 3.14). `planegcs` 0.9.6 builds from source
once Eigen and Boost are installed (`brew install eigen boost`). A smoke test solved a
constrained triangle, reported 0 degrees of freedom (2 after adding a free point), identified a
duplicated constraint as redundant, and returned the solved value of a non-driving distance
without changing the degrees of freedom.

Consequence: on macOS, cadder users need Eigen and Boost installed until `planegcs` ships macOS
wheels. TBD: document this in cadder's setup instructions, or contribute macOS wheels to
`planegcs`.

The licence of the format and the reference library is TBD; a permissive (non-copyleft)
open-source licence is the likely choice.

## 8. FreeCAD plugin

The plugin imports and exports CPSK documents as FreeCAD Sketcher sketches.

- **Supported geometry:** as in §5.6. Ellipses and B-splines MAY be added in a later version.
- **External geometry** (references to geometry outside the sketch) MUST be exported as
  ordinary geometry, construction or not.
- **Expressions:** Sketcher expressions SHOULD be converted to CPSK formulas (§5.10). An
  expression that cannot be converted is an unsupported feature.
- **Unsupported features:** the plugin MUST refuse to export a sketch that contains features
  it cannot represent, and report them.
- **Round trip:** FreeCAD → CPSK → FreeCAD MUST be lossless for the supported feature set.

The plugin uses a FreeCAD-specific namespace (§6.3) for deactivated constraints, which CPSK
readers skip as extension content. Converted external geometry is exported as blocked construction geometry
and needs no marking. Other details that improve round-tripping (identifiers, metadata,
variable limits, formulas as written) are kept on the FreeCAD side, in a hidden property of the
sketch, rather than in the file ([plan](../cpsk/freecad-plugin-plan.md), decisions D4, D6).

## 9. Testing

- **Acceptance test:** the 2020 V-slot profile, written in CPSK and solved, MUST match the
  current SVG profile (`cadder.hardware.vslot`): net area 161 mm² and the same outline
  coordinates.
- **Round-trip suite:** FreeCAD → CPSK → FreeCAD tests covering every supported primitive and
  constraint type (§8).
- **Error and warning tests:** one test document per error and warning in §7.2.

## 10. Future work

- A command-line tool around the Python API (§7.1).
- Direct PythonSCAD geometry output, with curve faceting set by the caller, in addition to
  SVG export.
- Ellipses and B-splines (§5.6, §8).
