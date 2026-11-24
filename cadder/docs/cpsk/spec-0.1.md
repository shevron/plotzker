# CPSK 0.1: Constraint-based Parametric Sketch format

| | |
|---|---|
| **Status** | Draft |
| **Version** | 0.1 |
| **Date** | 2026-11-23 |
| **Based on** | [RFC: CPSK](../rfc/parametric-sketch-format.md) |
| **Schema** | [`cpsk-0.1.xsd`](cpsk-0.1.xsd) |
| **Example** | [`examples/plate-with-hole.cpsk`](examples/plate-with-hole.cpsk) |
| **Implementations** | `cadder.cpsk` (reader, solver, SVG); [FreeCAD addon](../../freecad-addon/CPSK/README.md) (import, export) |

## Abstract

This document specifies version 0.1 of CPSK, an XML format for constraint-based parametric 2D
sketches. A CPSK document contains variables, geometric primitives with stored coordinates, and
constraints whose values are literals or formulas. The rationale and scope are in the RFC; this
document defines the syntax and semantics.

## 1. Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHOULD", "SHOULD NOT" and "MAY" are to be
interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

Items marked **TBD** are pending further research and experimentation. Choices made in this
draft that the RFC leaves open, or that deviate from it, are listed in
[Appendix A](#appendix-a-open-issues) for review.

### 1.1 Terminology

| Term | Meaning |
|---|---|
| Document | A CPSK file. |
| Reader | Software that parses a document. |
| Writer | Software that produces a document. |
| Solver | Software that computes geometry satisfying the constraints. |
| Consumer | Software that uses the solved geometry (e.g. cadder). |
| Primitive | A geometry element: point, line, circle or arc. |
| Curve | A line, circle or arc. |
| Driving constraint | A constraint the solver must satisfy. |
| Non-driving constraint | A dimensional constraint whose value is measured from the solved geometry (§9.2). |

## 2. Document structure

A document is a UTF-8 encoded XML 1.0 document. Its root element is `sketch`, in the CPSK
namespace:

```
https://github.com/shevron/plotzker/ns/cpsk
```

(TBD: final namespace URI, once cadder moves to its own repository. The URI identifies the
namespace and need not resolve.)

The root element contains, in this order, the following optional children:

| Element | Content | Section |
|---|---|---|
| `metadata` | Descriptive data | §5 |
| `variables` | `variable` elements | §6 |
| `geometry` | Primitives, which may contain nested constraints | §7, §9.4 |
| `constraints` | Top-level constraints | §9 |

A container element with no content (`variables`, `constraints`) MAY be omitted. An omitted
container is equivalent to an empty one.

Skeleton:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sketch xmlns="https://github.com/shevron/plotzker/ns/cpsk" version="0.1"
        unit-length="mm" unit-angle="deg">
  <metadata>...</metadata>
  <variables>...</variables>
  <geometry>...</geometry>
  <constraints>...</constraints>
</sketch>
```

Element and attribute names are lowercase, with words separated by hyphens (e.g. `point-on`,
`start-angle`), as in SVG. Formulas cannot contain hyphens in names, since `-` is the minus
operator; a property that corresponds to an attribute uses the same name with underscores
(e.g. attribute `start-angle`, property `start_angle`; §8.3). Identifiers (§3.1) are values,
not names, and follow their own syntax.

## 3. Lexical rules

### 3.1 Identifiers

An identifier matches `[A-Za-z_][A-Za-z0-9_]*` and is case-sensitive.

### 3.2 Reserved words

The following words are reserved. They MUST NOT be used as identifiers (`id` attributes).

| Category | Words | Section |
|---|---|---|
| Implicit references | `origin`, `x_axis`, `y_axis` | §8.1 |
| Parent reference | `self` | §8.4 |
| Constants | `pi` | §10.3 |
| Functions | `abs`, `sqrt`, `min`, `max`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2` | §10.3 |
| Units | `mm`, `cm`, `m`, `in`, `deg`, `rad` | §4.1 |

Words added to this list in later versions are reserved in those versions only. A reader MUST
report a reserved identifier as a load error.

Identifiers share one namespace per document: a variable, a primitive and a constraint MUST NOT
have the same identifier.

### 3.3 Numbers

A number is a decimal literal with an optional exponent: `12`, `-3.5`, `.25`, `1e-3`. `NaN` and
infinities are not allowed.

### 3.4 Literals with units

A literal is a number optionally followed by a unit, with optional whitespace between them:
`5`, `5mm`, `2.5 cm`, `30deg`. A literal without a unit is in the document unit of its context
(§4.2).

### 3.5 Booleans

Boolean attributes take the values `true` or `false`.

## 4. Root element: `sketch`

| Attribute | Required | Default | Value |
|---|---|---|---|
| `version` | Yes | | Format version, `0.1` for this specification. |
| `unit-length` | No | `mm` | Document length unit (§4.1). |
| `unit-angle` | No | `deg` | Document angle unit (§4.1). |

### 4.1 Units

| Kind | Unit | Factor |
|---|---|---|
| Length | `mm` | 1 mm |
| Length | `cm` | 10 mm |
| Length | `m` | 1000 mm |
| Length | `in` | 25.4 mm (exact) |
| Angle | `deg` | π/180 rad |
| Angle | `rad` | 1 rad |

### 4.2 Unit conversion

A reader MUST convert every literal with a unit to the document unit of the same kind before
use. After conversion, all values are plain numbers in document units.

A unit of the wrong kind for its context is an error where the context is known, i.e. when an
attribute value is a single literal (e.g. `value="30deg"` on a `length` variable, or on a
`distance` constraint). Inside larger formulas a unit converts its literal only; version 0.1
does not perform dimensional analysis (Appendix A, A6).

## 5. Metadata

The optional `metadata` element contains any of the following children, in any order:

| Element | Count | Content |
|---|---|---|
| `title` | 0–1 | Short name |
| `description` | 0–1 | Free text |
| `author` | 0 or more | Free text |
| `created` | 0–1 | ISO 8601 date or date-time |
| `modified` | 0–1 | ISO 8601 date or date-time |
| `tag` | 0 or more | Free-form tag |

Metadata does not affect solving.

## 6. Variables

```xml
<variables>
  <variable id="width" type="length" value="40" min="10" max="200"
            description="Plate width"/>
  <variable id="height" type="length" value="2.5cm"/>
  <variable id="ratio" value="width / height"/>
</variables>
```

| Attribute | Required | Default | Value |
|---|---|---|---|
| `id` | Yes | | Identifier (§3.1). |
| `type` | No | `number` | `number` (dimensionless), `length` or `angle`. |
| `value` | Yes | | Default value: a formula (§10). |
| `min` | No | | Lower limit: a literal (§3.4). |
| `max` | No | | Upper limit: a literal (§3.4). |
| `description` | No | | Free text. |

Rules:

- A `number` variable's value and limits MUST NOT carry a unit. A `length` or `angle`
  variable's literals MAY carry a unit of the matching kind.
- A variable's value MAY be a formula that references other variables (a derived variable).
- A caller MAY override a variable's value with a literal at solve time. A reader MUST report an
  error if a value, default or overridden, is outside `[min, max]`. Derived variables are
  re-evaluated after overrides.

## 7. Geometry

### 7.1 Coordinate system

Coordinates are in a right-handed system with the y axis pointing up and the origin at
(0, 0). Angles are measured counterclockwise from the positive x axis. There is no global
transform.

### 7.2 Common attributes

| Attribute | Required | Default | Value |
|---|---|---|---|
| `id` | No | | Identifier. Required to reference the primitive. |
| `construction` | No | `false` | If `true`, the primitive takes part in solving but is not rendered or exported. |

A primitive MAY contain constraints as child elements (nested constraints, §9.4).

### 7.3 Stored coordinates

Every primitive stores the coordinates that define it, as attributes. Stored coordinates:

- MUST be plain numbers (§3.3) in document units: no unit suffixes, no formulas.
- Are the solver's initial values. A solver MUST start from them.
- Are the last solved state. A writer that solves a document and writes it back SHOULD write
  the solved coordinates.
- Need not satisfy the constraints (RFC §5.3).

### 7.4 Primitives

Names follow SVG where SVG has an equivalent element.

| Element | Attributes | Geometry |
|---|---|---|
| `point` | `x`, `y` | A point. |
| `line` | `x1`, `y1`, `x2`, `y2` | Segment from (`x1`, `y1`) to (`x2`, `y2`). Its direction is start to end. |
| `circle` | `cx`, `cy`, `r` | Circle with centre (`cx`, `cy`) and radius `r` > 0. |
| `arc` | `cx`, `cy`, `r`, `start-angle`, `end-angle` | Circular arc with centre (`cx`, `cy`) and radius `r` > 0, running counterclockwise from `start-angle` to `end-angle` (document angle unit). |

Arc rules:

- An arc always runs counterclockwise, as in FreeCAD. Its sweep is `end-angle` minus
  `start-angle`, normalised to (0, 360°].
- Its start and end points are derived: start = (`cx` + `r`·cos θs, `cy` + `r`·sin θs), with
  θs = `start-angle`, and likewise for the end point with `end-angle`.

A line owns its two end points. Connected lines are joined with `coincident` constraints; they
do not share point objects. Polylines, polygons, rectangles and similar MUST be written as their
constituent primitives and constraints.

```xml
<geometry>
  <line id="base" x1="0" y1="0" x2="40" y2="0"/>
  <arc id="fillet" cx="40" cy="5" r="5" start-angle="-90" end-angle="0"/>
  <circle id="hole" cx="20" cy="12.5" r="4"/>
  <line id="diag" construction="true" x1="0" y1="0" x2="40" y2="25"/>
</geometry>
```

## 8. References

Constraints refer to primitives and to points on them by reference.

### 8.1 Implicit references

These references exist in every document without being declared. They are fixed and cannot be
modified by the solver.

| Reference | Kind | Geometry |
|---|---|---|
| `origin` | Point | (0, 0) |
| `x_axis` | Line | The x axis, direction +x |
| `y_axis` | Line | The y axis, direction +y |

They correspond to FreeCAD's sketch root point and horizontal and vertical axes.

### 8.2 Point and curve references

| Reference | Refers to |
|---|---|
| `<id>` of a `point` | The point |
| `<id>` of a curve | The curve (edge) |
| `<id>.start`, `<id>.end` | End points of a `line` or `arc` |
| `<id>.center` | Centre of a `circle` or `arc` |

### 8.3 Properties

Properties are read with `<ref>.<property>`, e.g. `l1.length`, `hole.radius`,
`l1.start.x`.

| Reference | Properties |
|---|---|
| Point, or a point reference | `x`, `y` |
| `line` | `length`, `angle` (direction, from +x) |
| `circle` | `radius`, `diameter` |
| `arc` | `radius`, `diameter`, `start_angle`, `end_angle`, `sweep` |

Property names use underscores, since `-` is the minus operator in formulas. `start_angle`
and `end_angle` correspond to the arc attributes `start-angle` and `end-angle`.

Properties are values of the solved geometry. In version 0.1 formulas in the document MUST NOT
reference them (§10.5); the reference library exposes them to consumers after solving, using the
same syntax.

### 8.4 Parent reference: `self`

Inside a nested constraint (§9.4), `self` refers to the parent primitive, and `self.start`,
`self.end` and `self.center` to its points (§8.2). `self` MUST NOT be used outside a nested
constraint, and MUST NOT be used in formulas.

### 8.5 Resolution

References are resolved after the whole document is parsed. A reference MAY refer to a
primitive that appears later in the document.

## 9. Constraints

### 9.1 Common attributes

| Attribute | Applies to | Required | Default | Value |
|---|---|---|---|---|
| `id` | All | No | | Identifier. Required to reference the constraint's value. |
| `value` | Dimensional | If driving | | Formula (§10). |
| `driving` | Dimensional | No | `true` | `false` makes the constraint non-driving (§9.2). |

Dimensional constraints are `distance`, `distance-x`, `distance-y`, `radius`, `diameter` and
`angle`. The others are geometric.

### 9.2 Non-driving constraints

A dimensional constraint with `driving="false"` does not constrain the geometry. The solver
measures its value from the solved geometry, and it is excluded from the degrees of freedom
count. Its `value` attribute is optional; if present it MUST be a literal holding the last
measured value, and readers MUST NOT use it as an input.

This corresponds to FreeCAD reference constraints and SolveSpace reference dimensions. TBD:
final naming (RFC §5.8).

### 9.3 Constraint types

Operand attributes: `of` for a single operand; `a` and `b` for two; `about`, `point` and
`object` where named below. Each operand is a reference (§8). Operand kinds: *P* point,
*L* line, *C* circle, *A* arc.

| Element | Operands | Value | Meaning | FreeCAD |
|---|---|---|---|---|
| `coincident` | `a`, `b`: P | | Points coincide. | Coincident |
| `point-on` | `point`: P; `object`: L, C, A | | Point lies on the object's supporting line or circle. | PointOnObject |
| `horizontal` | `of`: L, or `a`, `b`: P | | Line is horizontal, or points have equal y. | Horizontal |
| `vertical` | `of`: L, or `a`, `b`: P | | Line is vertical, or points have equal x. | Vertical |
| `parallel` | `a`, `b`: L | | Lines are parallel. | Parallel |
| `perpendicular` | `a`, `b`: L | | Lines are perpendicular. | Perpendicular |
| `perpendicular` | `a`, `b`: one L and one C or A, in either order | | The line's supporting line passes through the centre: it is normal to the curve. | Perpendicular (edge to edge) |
| `perpendicular` | `a`, `b`: end points (`.start`/`.end`) of one L and one A, in either order | | End points coincide and the curves are perpendicular there. | Perpendicular (endpoint to endpoint) |
| `tangent` | `a`, `b`: L, C, A (not both L) | | Curves are tangent. | Tangent |
| `tangent` | `a`, `b`: end points (`.start`/`.end`) of L or A | | End points coincide and the curves are tangent there. | Tangent (endpoint to endpoint) |
| `equal` | `a`, `b`: both L, or both C/A | | Equal length, or equal radius. | Equal |
| `symmetric` | `a`, `b`: P; `about`: P or L | | `a` and `b` are symmetric about a point (its midpoint) or a line. | Symmetric |
| `block` | `of`: any primitive | | The primitive is fixed at its stored coordinates. | Block |
| `distance` | `of`: L | length | Line length. | Distance |
| `distance` | `a`, `b`: P | length | Distance between points. | Distance |
| `distance` | `a`, `b`: one P and one L, in either order | length | Distance from the point to the line's supporting line. | Distance |
| `distance-x` | `a`, `b`: P | length | Signed horizontal distance `b.x - a.x`. | DistanceX |
| `distance-y` | `a`, `b`: P | length | Signed vertical distance `b.y - a.y`. | DistanceY |
| `radius` | `of`: C, A | length | Radius. | Radius |
| `diameter` | `of`: C, A | length | Diameter. | Diameter |
| `angle` | `of`: A | angle | Arc sweep. | Angle |
| `angle` | `a`, `b`: L | angle | Angle from `a`'s direction to `b`'s, counterclockwise. | Angle |

Signed and directional constraints (`distance-x`, `distance-y`, `angle` between lines) measure
from `a` to `b`. Absolute positions and directions are written against the implicit
references (§8.1):

| FreeCAD | CPSK |
|---|---|
| DistanceX on a point `p` | `<distance-x a="origin" b="p"/>` |
| DistanceX on a line `l` | `<distance-x a="l.start" b="l.end"/>` |
| Angle on a line `l` | `<angle a="x_axis" b="l"/>` |
| Lock on a point `p` | `distance-x` and `distance-y` from `origin` |

Constraints that version 0.1 does not define (e.g. FreeCAD SnellsLaw, InternalAlignment,
Weight) are unsupported features (RFC §8).

These conventions match FreeCAD 1.1.3 and PlaneGCS for every constraint form above
([freecad-conventions.md](freecad-conventions.md)). Tangency between curves is external or
internal, and tangency between end points keeps the relative direction, as in the stored
coordinates (§7.3). Likewise, perpendicularity between end points keeps the side the curve turns
to, as in the stored coordinates.

Top-level form:

```xml
<constraints>
  <coincident a="base.start" b="origin"/>
  <horizontal of="base"/>
  <distance id="w" of="base" value="width"/>
  <tangent a="base.end" b="fillet.start"/>
  <radius of="fillet" value="w / 8"/>
</constraints>
```

### 9.4 Nested constraints

A constraint MAY be written as a child element of a primitive, its *parent*. The same
constraints written nested (and preferred, §11.4):

```xml
<line id="base" x1="0" y1="0" x2="40" y2="0">
  <coincident a="self.start" b="origin"/>
  <horizontal/>
  <distance id="w" value="width"/>
  <tangent a="self.end" b="fillet.start"/>
</line>
<arc id="fillet" cx="40" cy="5" r="5" start-angle="-90" end-angle="0">
  <radius value="w / 8"/>
</arc>
```

Rules:

1. A nested constraint MAY omit one operand attribute. The omitted operand is the parent.
2. `self` and its points (§8.4) MAY be used in any operand.
3. A nested constraint MUST reference its parent, through an omitted operand or through
   `self`. A nested constraint that does not is a load error.
4. A nested constraint MUST NOT have an `of` attribute; `of` is always the omitted operand.
5. A nested constraint is equivalent to the top-level constraint obtained by writing the
   omitted operand as the parent and replacing `self` with the parent. The parent therefore
   needs an `id` only if other constraints reference it.
6. The omitted operand is resolved by kind, as at top level: an omitted operand of the wrong
   kind is a load error (e.g. `<coincident b="q"/>` in a `line`, whose parent is not a point).
7. For `distance` and `angle`: when neither `a` nor `b` is given, the omitted operand is
   `of`; when one is given, the omitted operand is the other.
8. Attributes other than operands (`id`, `value`, `driving`) are unchanged. A nested
   constraint's `id` belongs to the document-wide identifier namespace.

Allowed nested forms. *p*, *q* are points, *l* a line, *c* a circle, *k* an arc; "—" means the
constraint cannot be nested in that primitive.

| Constraint | In `point` | In `line` | In `circle` | In `arc` |
|---|---|---|---|---|
| `coincident` | `<coincident b="q"/>` | `<coincident a="self.end" b="q"/>` | `<coincident a="self.center" b="q"/>` | `a="self.start"`, `self.end` or `self.center` |
| `point-on` | `<point-on object="l"/>`: self lies on `l` | `<point-on point="p"/>`: `p` lies on self | `<point-on point="p"/>`, or `<point-on point="self.center" object="l"/>` | as `circle` |
| `horizontal`, `vertical` | `<horizontal b="q"/>` | `<horizontal/>` | `<horizontal a="self.center" b="q"/>` | as `circle`, or with `self.start`/`self.end` |
| `parallel` | — | `<parallel b="l"/>` | — | — |
| `perpendicular` | — | `<perpendicular b="l"/>`, `<perpendicular b="c"/>`: through the centre; `<perpendicular a="self.end" b="k.start"/>` | `<perpendicular b="l"/>` | `<perpendicular b="l"/>`; `<perpendicular a="self.end" b="l.start"/>` |
| `tangent` (curves) | — | `<tangent b="c"/>` | `<tangent b="l"/>` | `<tangent b="l"/>` |
| `tangent` (end points) | — | `<tangent a="self.end" b="k.start"/>` | — | `<tangent a="self.end" b="l.start"/>` |
| `equal` | — | `<equal b="l"/>`: length | `<equal b="c"/>`: radius | `<equal b="k"/>`: radius |
| `symmetric` | `<symmetric a="p" b="q"/>`: about self | `<symmetric a="p" b="q"/>`: mirrored about self; or `<symmetric a="self.start" b="self.end" about="p"/>` | `<symmetric a="p" b="q" about="self.center"/>` | as `circle` |
| `block` | `<block/>` | `<block/>` | `<block/>` | `<block/>` |
| `distance` | `<distance b="q"/>`, `<distance b="l"/>` | `<distance/>`: length; `<distance b="p"/>`: point to line | `<distance a="self.center" b="p"/>` | as `circle` |
| `distance-x`, `distance-y` | `<distance-x b="q"/>`: `q.x - self.x`; `<distance-x a="origin"/>`: `self.x` | `<distance-x a="self.start" b="self.end"/>`: width | `<distance-x a="self.center" b="p"/>` | as `circle` |
| `radius`, `diameter` | — | — | `<radius/>` | `<radius/>` |
| `angle` | — | `<angle b="l"/>`: from self to `l`; `<angle a="x_axis"/>`: direction | — | `<angle/>`: sweep |

## 10. Formulas

### 10.1 Where formulas appear

The `value` attribute of variables and driving constraints is a formula. A single literal or
reference is a valid formula.

### 10.2 Grammar

In EBNF; whitespace is allowed between tokens.

```ebnf
formula   = sum ;
sum       = product , { ( "+" | "-" ) , product } ;
product   = unary , { ( "*" | "/" ) , unary } ;
unary     = ( "+" | "-" ) , unary | power ;
power     = primary , [ "^" , unary ] ;          (* right-associative *)
primary   = literal | call | reference | "(" , formula , ")" ;
literal   = number , [ unit ] ;
call      = function , "(" , formula , { "," , formula } , ")" ;
reference = identifier , { "." , identifier } ;
unit      = "mm" | "cm" | "m" | "in" | "deg" | "rad" ;
```

Precedence, from highest: `^`, unary `+`/`-`, `*`/`/`, binary `+`/`-`. So `-2^2` is `-4`, and
`2^3^2` is `2^9`. There is no implicit multiplication: a unit may follow only a number.

### 10.3 Functions and constants

| Name | Arguments | Result |
|---|---|---|
| `abs(x)`, `sqrt(x)` | 1 | |
| `min(x, y, ...)`, `max(x, y, ...)` | 2 or more | |
| `sin(a)`, `cos(a)`, `tan(a)` | 1 angle | Argument in the document angle unit. |
| `asin(x)`, `acos(x)`, `atan(x)` | 1 | Result in the document angle unit. |
| `atan2(y, x)` | 2 | Result in the document angle unit. |
| `pi` | constant | π (a number, not an angle). |

### 10.4 Evaluation

- Formulas are evaluated before solving, in an order derived from their references. A reader
  MUST report circular references as errors.
- A bare identifier refers to a variable's value or to a driving constraint's value.
- Errors at evaluation (division by zero, `sqrt` of a negative number, domain errors) are load
  errors.

### 10.5 Restrictions in version 0.1

A formula MUST NOT reference a geometric property (§8.3) or a non-driving constraint. Both are
results of solving, and a formula that depends on them would make the evaluation depend on the
solve. A reader MUST report such a reference as an error. (TBD: lifting this restriction, RFC
§5.8; Appendix A, A1.)

## 11. Processing

### 11.1 Errors and warnings

As in RFC §7.2: load errors stop processing; solve errors stop solving; warnings never stop
processing and MUST be reported in a structured form.

| Stage | Errors | Warnings |
|---|---|---|
| Load | Malformed XML; invalid structure or attribute values; duplicate or reserved identifier; unresolved reference; operand of the wrong kind; unit of the wrong kind (§4.2); circular reference; formula evaluation error; variable outside its limits; forbidden reference (§10.5); `self` outside a nested constraint (§8.4); nested constraint that does not reference its parent, or has `of` (§9.4) | Unknown element or attribute (§11.3); newer minor version (§11.2) |
| Solve | Conflicting constraints; failure to converge | Remaining degrees of freedom; redundant constraints |

### 11.2 Versions

`version` has the form `MAJOR.MINOR`. A reader for version X.Y:

- MUST reject a document with a different major version (before 1.0, a different minor
  version counts as a different major version);
- MUST warn about a document with a newer minor version, and process it.

### 11.3 Unknown content and extensions

- An element or attribute in the CPSK namespace, or an unqualified attribute, that this
  specification does not define is *unknown*. A reader MUST NOT silently ignore unknown
  content: it MUST at least warn, and MAY reject the document.
- Elements and attributes in other namespaces are *extensions* (e.g. FreeCAD-specific data,
  RFC §8). They are not unknown content: a reader MAY ignore them without a warning, and a
  writer that rewrites a document SHOULD preserve them.

### 11.4 Writing

A writer:

- MUST write `version`;
- SHOULD write numbers with enough digits to round-trip a binary64 value;
- SHOULD preserve identifiers, element order and extension content when rewriting a document;
- SHOULD omit empty containers (§2);
- SHOULD write every constraint nested (§9.4), in a canonical place, so that a sketch has one
  encoding:
  1. `symmetric`: under the primitive that is, or owns, `about`;
  2. a constraint whose operands involve one primitive only (besides implicit references):
     under that primitive;
  3. otherwise: under the operand primitive that comes first in document order. In a closed
     chain of lines written in order, each joint is held by the earlier line, and the closing
     joint by the first line.

  Within a primitive, the writer SHOULD omit the operand that is the parent itself, and use
  `self` only for its points.

## 12. Schema and examples

- [`cpsk-0.1.xsd`](cpsk-0.1.xsd) is an XML Schema 1.0 for the structure in §2 to §9. It checks
  element structure, attribute presence, identifier syntax and uniqueness, literal syntax, and
  which constraints may be nested in each primitive. It does not check reference resolution,
  operand kinds, reserved words, the nesting rules of §9.4 or formula syntax; readers check
  those.
- [`examples/plate-with-hole.cpsk`](examples/plate-with-hole.cpsk): a fully constrained
  rectangular plate with a centred hole, written in the canonical nested form, with variables,
  a derived variable and a non-driving constraint.

## Appendix A: Open issues

Choices this draft makes where the RFC is open or differs from it. Each needs confirmation.

| # | Issue | Draft choice | Alternative |
|---|---|---|---|
| A1 | Formulas reading solved values (RFC §5.8, §5.9) | Forbidden in 0.1 (§10.5). Properties are available to consumers only. FreeCAD also refuses expressions that read reference constraints of the same sketch. | Allow, with partial or iterative solving and solve-level cycle detection. |
| A2 | Non-driving constraint naming (RFC §5.8) | Attribute `driving="false"`, the term used by FreeCAD and PlaneGCS. | A separate element, e.g. `<measure>`. |
| A3 | `mid` point references (RFC §5.9 lists them) | Dropped: FreeCAD cannot reference a line midpoint, so they would break the round trip. Use `symmetric` instead. | Keep them; the plugin adds construction geometry. |
| A4 | Implicit references `origin`, `x_axis`, `y_axis` (not in the RFC) | Added, to match FreeCAD's root point and axes. | |
| A5 | `version` (RFC §6.3: SHOULD) | REQUIRED. | Optional, defaulting to the reader's version. |
| A6 | Type rules (RFC §5.4 TBD) | Units checked only for single-literal values; no dimensional analysis in formulas. FreeCAD accepts a mismatched result (a length × length assigned to a length) but rejects sums of a length and a unitless number; the FreeCAD addon infers dimensions and adds `mm` or `°` to such numbers on import. | Full dimensional analysis. |
| A7 | Trigonometric angle units (RFC §5.10 TBD) | Document angle unit (FreeCAD uses degrees for unitless arguments, the same in degree documents). | Always radians. |
| A8 | Length units (RFC §5.2 TBD) | `mm`, `cm`, `m`, `in`. | Add `ft`, `um`. |
| A9 | Formula property names | Underscores (`start_angle`), since names in formulas cannot contain `-`. XML names use hyphens (decided). | Single-word property names only (e.g. `begin`, `finish`), so XML and formula names are identical. |
| A10 | Shared end points | Each line or arc owns its end points; connections are `coincident` constraints (as FreeCAD). | Shared `point` elements referenced by lines. |
| A11 | Foreign namespaces (RFC §6.3 TBD) | Extensions, not unknown content (§11.3). The FreeCAD addon uses one for deactivated constraints (`<freecad:inactive>`). | |
| A12 | Constraint coverage | The FreeCAD subset in §9.3. Perpendicular between a line and a circle or arc (edge to edge, and arc and line end points) was added on 2026-11-23. Distances between circles and lines, other perpendicular forms (via a point, end point to edge, between curves) and arc length are left for later; the FreeCAD addon refuses to export them and lists them. | Include them in 0.1. |
| A13 | Namespace URI | Placeholder under the plotzker repository. | A URI under a domain owned by the project. |
| A14 | `^` precedence and associativity (§10.2) | **Decided (2026-11-23).** Mathematical convention: `^` binds tighter than unary minus (`-2^2` = −4) and is right-associative (`2^3^2` = 512), as in Python. FreeCAD differs (4 and 64), so the plugin adds parentheses when translating. | FreeCAD's convention, so formulas translate unchanged. |
| A15 | Identifiers that FreeCAD reads as units or constants (`t`, `h`, `s`, `g`, `l`, `e`, `N`, …), found in plugin phase 3 | Allowed. The FreeCAD addon renames them on import (`t` → `t_`) and restores them on export (plan D9). | Reserve FreeCAD's unit names too (§3.2), so documents import unchanged; this would forbid common names such as `t` and `h`. |
| A16 | Canonical arc angles (§11.4), found in plugin phase 3 | Not specified: any `start-angle` and `end-angle` with the same sweep describe the same arc. The FreeCAD addon writes the start in [−180°, 180°) and the end at start + sweep, so files survive FreeCAD's [0°, 360°) normalization. | Make that range the canonical form in §11.4. |
