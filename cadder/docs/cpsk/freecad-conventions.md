# FreeCAD conventions for CPSK (phase 0 results)

Phase 0 of the [FreeCAD plugin plan](freecad-plugin-plan.md): FreeCAD's Sketcher conventions,
checked against the [spec](spec-0.1.md) before writing the plugin. Run on 2026-11-23 with
FreeCAD 1.1.3 (Python 3.11.14) headless (`freecadcmd`) and `cadder.cpsk` 0.1 (PlaneGCS through
`planegcs` 0.9.6).

## Method

39 small sketches, one or more per FreeCAD constraint form in plan §4.2, each fully constrained
and seeded off its solution. Each was solved twice:

1. in FreeCAD, built with `Sketcher.Constraint` from the case's FreeCAD form;
2. in `cadder.cpsk`, from a CPSK document produced by the plan's §4.2 mapping (a prototype of the
   exporter's mapping).

The solved geometry was compared (1e-7 mm, 1e-6°), and sign-sensitive cases were also checked
against the spec's definitions. Expression behavior was probed on a VarSet and on sketch
constraints.

## Constraint mapping: all 39 cases agree

| Case | Result |
|---|---|
| Coincident; point on a line (on its extension), circle, arc | Agree. Point on an arc lies on its **full circle**, as spec §9.3 says |
| Horizontal / vertical, of a line and of two points | Agree |
| Parallel, perpendicular, equal (lines; circle and arc) | Agree |
| Distance: line length, two points, point to line | Agree. Point to line is **unsigned** (a point seeded below the line stays below) |
| DistanceX / DistanceY: line, single point, two points, negative values | Agree. **Signed**: `end − start`, the point's coordinate, `b − a`; FreeCAD stores negative values as given |
| Lock (DistanceX + DistanceY on a point) | Agree |
| Angle of a line: 30°, −30°, 150° | Agree. Direction from +x, counterclockwise, signed |
| Angle between lines, including a first line pointing −x and −30° | Agree. **From the first line's direction to the second's, counterclockwise**: a first line pointing −x plus 30° gives 210° |
| Radius, diameter (circle, arc); arc sweep | Agree |
| Tangent: line–circle, line–arc, circle–circle external and internal | Agree. **Internal or external tangency follows the stored geometry** in both solvers |
| Tangent between end points: line–arc at the arc's start and at its end | Agree. FreeCAD stores the locked direction in `Value` (±π/2 here); CPSK derives it from the stored coordinates, and FreeCAD sets it itself when the constraint is added without a value |
| Symmetric about a line, about a point; a line's end points about a point | Agree |
| Block | Agree |
| Non-driving distance | Agree: both measure 5 |

Arc angles: FreeCAD reports `FirstParameter` in [0, 2π) (e.g. 270° to 360°), `cadder.cpsk` in
[−180°, 180°) (−90° to 0°); the same arc.

## Expressions

| Probe | FreeCAD | CPSK 0.1 | Consequence |
|---|---|---|---|
| `2.5 cm`, `2.5cm`, `1 in`, `1in` | 25, 25, 25.4, 25.4 mm | Same | Literals translate as they are |
| `30 deg`, `30 °`, `0.5 rad` | 30°, 30°, 28.65° | Same | `°` ↔ `deg` |
| Unitless number in a length / angle | **mm / degrees** | The document units | Direct translation only for `unit-length="mm"`, `unit-angle="deg"` (plan D8) |
| `sin(30)`, `atan2(1, 1)`, `asin(0.5)` | Degrees in and out | Document angle unit (spec A7) | Same for degree documents |
| `min`, `max`, `abs`, `sqrt`, `pi`, `1e1`, `.5` | Supported | Same | Translate as they are |
| `-2^2` | **4** (unary minus binds tighter) | −4 | **Differs**: translation must add parentheses (spec A14) |
| `2^3^2` | **64** (left-associative) | 512 (right-associative) | **Differs**: as above |
| `Vars.width`, `<<Vars>>.width` | VarSet property | Variable `width` | D2 works as planned |
| `Constraints.w`, `.Constraints.w` | Value of named constraint `w` | `w` | Translate both spellings |
| Reference to a **non-driving** constraint of the same sketch | **Refused**: "Reference constraint from this sketch cannot be used in this expression" | Refused (spec §10.5) | FreeCAD has the same rule as spec A1 |
| Length × length assigned to a length constraint | Accepted, no unit error | No dimensional analysis (A6) | Lower risk than plan §9 assumed |
| A constraint named `m` | Parse error: `m` is read as meter | `m` is reserved (spec §3.2) | Reserved words matter for FreeCAD too |

## Outcomes

- Spec §9.3 TBD (sign and direction conventions) is resolved: the spec's definitions match
  FreeCAD 1.1.3 and PlaneGCS for every constraint form in plan §4.2.
- Spec **A14** (decided): keep the spec's `^` convention; the plugin adds parentheses when
  translating.
- Plan **D8** (decided): the plugin imports only mm/degree documents for now; export always
  writes mm and degrees.
- Plan risk "FreeCAD rejects CPSK formulas that mix units" is downgraded: FreeCAD accepted a
  length × length value for a length constraint.

Later phases found more FreeCAD behaviour (details in the
[plan](freecad-plugin-plan.md)'s "as built" notes):

- FreeCAD reads many short names as units or constants in expressions (`t`, `h`, `s`, `g`, `l`,
  `e`, `m`, `min`, `in`, capitals such as `N`): a constraint or variable with such a name cannot
  carry or be used in an expression (plan D9, spec A15). `App.Units.Quantity(name)` tells them.
- FreeCAD checks units in sums (`Constraints.s - 6` fails: length minus number), though not in
  assignments (spec A6).
- FreeCAD stores expressions in its own form: `;` between function arguments, `^` with spaces,
  `1e1` as `10`.
- Arc parameters are kept in [0, 2π).
- With a `package.xml`, FreeCAD 1.1 runs an addon's `Init.py` only for `<workbench>` items.
- `addConstraint` does not solve: constraints can be added, then made non-driving or
  deactivated, before the next recompute.
- A wrong `Sketcher.Constraint` signature (e.g. `Block` with a PosId) crashes FreeCAD instead of
  raising an error.

The 39 cases are kept as plain data in
[`cadder/tests/cpsk_freecad/cases.py`](../../tests/cpsk_freecad/cases.py), the corpus for the
plugin's tests (phase 2). The probe scripts (FreeCAD and CPSK runners, expression probes) were
throwaway; phase 2 turns them into tests.
