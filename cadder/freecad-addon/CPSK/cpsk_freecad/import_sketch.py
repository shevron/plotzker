"""CPSK document → FreeCAD sketch (plugin plan §4, phase 3).

:func:`from_document` turns a document into a :class:`~cpsk_freecad.sketch_data.SketchData`
(the same plain data the exporter reads), so the mapping runs without FreeCAD;
:func:`import_sketch` creates the sketch and its VarSet from it in a FreeCAD document.

- Primitives become geometry in document order (GeoId = index); constraints are added in
  document order with FreeCAD's argument forms (plan §4.2, read backwards).
- Variables become properties of one ``App::VarSet`` per imported sketch (D2): ``length`` →
  ``App::PropertyDistance``, ``angle`` → ``App::PropertyAngle``, ``number`` →
  ``App::PropertyFloat``. Formulas other than a plain number become FreeCAD expressions.
- Ids, metadata and variable limits are kept in the sketch's hidden ``CpskData`` property so that
  export writes them back (D4). An id FreeCAD reads as a unit or constant (``t``, ``h``, ``e``,
  ``min``, …) cannot carry or be used in an expression: it is renamed (``t`` → ``t_``) with a
  warning, and export restores it (D9).
- Constraints in ``<freecad:inactive>`` are added deactivated (D6).
- Only documents in millimetres and degrees are imported (D8). Comments and extension content
  other than FreeCAD's are not kept.
"""

from __future__ import annotations

import copy
import dataclasses
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path as FilePath
from typing import Any

from cpsk_core import (
    CpskError,
    CpskLoadError,
    Diagnostic,
    Document,
    Element,
    Stage,
    compile_document,
)
from cpsk_core import model as cpsk
from cpsk_core.document import Node, read
from cpsk_core.errors import error, warning
from cpsk_core.formula import names, parse
from cpsk_freecad.export_sketch import FREECAD_NAMESPACE
from cpsk_freecad.expressions import is_plain_number, to_freecad
from cpsk_freecad.sketch_data import (
    KEPT_PROPERTY,
    UNDEFINED,
    Constraint,
    Geometry,
    Kept,
    SketchData,
    Variable,
    VarSet,
)

_PROPERTY_TYPES = {
    "length": "App::PropertyDistance",
    "angle": "App::PropertyAngle",
    "number": "App::PropertyFloat",
}
_TYPES = {
    "coincident": "Coincident",
    "point-on": "PointOnObject",
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "parallel": "Parallel",
    "perpendicular": "Perpendicular",
    "tangent": "Tangent",
    "equal": "Equal",
    "symmetric": "Symmetric",
    "block": "Block",
    "distance": "Distance",
    "distance-x": "DistanceX",
    "distance-y": "DistanceY",
    "radius": "Radius",
    "diameter": "Diameter",
    "angle": "Angle",
}
_POSITIONS = {None: 0, "start": 1, "end": 2, "center": 3}
_VARIABLE_GROUP = "Variables"


def import_sketch(doc: Any, path: str | FilePath) -> tuple[Any, list[Diagnostic]]:
    """Import a CPSK file into a FreeCAD document; returns the sketch and the warnings.

    The sketch is labelled with the document's title (or the file name); its variables go to a
    new VarSet. Raises :class:`cpsk_core.CpskLoadError` (nothing is created then).
    """
    document = read(path)
    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    varset = None
    container = document.container("variables")
    if container is not None and any(container.elements("variable")):
        varset = doc.addObject("App::VarSet", f"{sketch.Name}Variables")
    try:
        data, warnings = from_document(
            document,
            sketch_name=sketch.Name,
            varset_name=varset.Name if varset is not None else "",
            is_unit=_is_freecad_unit,
        )
    except CpskError:
        for created in (sketch, varset):
            if created is not None:
                doc.removeObject(created.Name)
        raise
    build(sketch, varset, data, label=data.label or FilePath(path).stem)
    doc.recompute()
    return sketch, warnings


def build(sketch: Any, varset: Any, data: SketchData, *, label: str) -> None:
    """Fill a new sketch (and VarSet) from imported data."""
    import Part  # FreeCAD's modules: only here, so the rest runs without FreeCAD
    import Sketcher
    from FreeCAD import Vector

    sketch.Label = label
    if varset is not None and data.varsets:
        found = data.varsets[0]
        varset.Label = found.label or f"{label} variables"
        for variable in found.variables:
            varset.addProperty(variable.type, variable.name, _VARIABLE_GROUP, variable.description)
            setattr(varset, variable.name, variable.value)
        for variable in found.variables:
            if variable.expression is not None:
                varset.setExpression(variable.name, variable.expression)
    for geometry in data.geometry:
        sketch.addGeometry(_part(geometry, Part, Vector), geometry.construction)
    created = []
    for constraint in data.constraints:
        made = Sketcher.Constraint(constraint.type, *_arguments(constraint))
        if constraint.name:
            made.Name = constraint.name
        created.append(made)
    if created:
        sketch.addConstraint(created)  # FreeCAD solves on recompute, after the flags are set
    for index, constraint in enumerate(data.constraints):
        if not constraint.driving:
            sketch.setDriving(index, False)
        if not constraint.active:
            sketch.setActive(index, False)
    for name, expression in data.expressions.items():
        sketch.setExpression(f"Constraints.{name}", expression)
    geometry_ids = [sketch.getGeometryId(i) for i in range(len(sketch.Geometry))]
    sketch.addProperty(
        "App::PropertyString", KEPT_PROPERTY, "CPSK", "CPSK round-trip data", 0, False, True
    )
    setattr(sketch, KEPT_PROPERTY, data.kept.to_json(geometry_ids))


def _is_freecad_unit(name: str) -> bool:
    """Whether FreeCAD's expression parser reads ``name`` as a unit or a constant (D9)."""
    from FreeCAD import Units

    try:
        Units.Quantity(name)
    except Exception:  # noqa: BLE001: FreeCAD raises its own error types
        return False
    return True


def _part(geometry: Geometry, part: Any, vector: Any) -> Any:
    c = geometry.coords
    if geometry.kind == "point":
        return part.Point(vector(c[0], c[1], 0))
    if geometry.kind == "line":
        return part.LineSegment(vector(c[0], c[1], 0), vector(c[2], c[3], 0))
    circle = part.Circle(vector(c[0], c[1], 0), vector(0, 0, 1), c[2])
    if geometry.kind == "circle":
        return circle
    return part.ArcOfCircle(circle, math.radians(c[3]), math.radians(c[4]))


def _arguments(constraint: Constraint) -> list[Any]:
    """``Sketcher.Constraint`` arguments: an edge as its GeoId, a point as (GeoId, PosId)."""
    args: list[Any] = []
    for geo, pos in (
        (constraint.first, constraint.first_pos),
        (constraint.second, constraint.second_pos),
        (constraint.third, constraint.third_pos),
    ):
        if geo != UNDEFINED:
            args += [geo] if pos == 0 else [geo, pos]
    if constraint.type in {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}:
        args.append(constraint.value)
    return args


# ----- The mapping, without FreeCAD -----


def from_document(
    document: Document,
    *,
    sketch_name: str = "Sketch",
    varset_name: str = "SketchVariables",
    is_unit: Callable[[str], bool] = lambda name: False,
) -> tuple[SketchData, list[Diagnostic]]:
    """The sketch data for a CPSK document, and the warnings (see the module docstring).

    ``sketch_name`` and ``varset_name`` are the FreeCAD object names expressions refer to;
    ``is_unit`` says whether FreeCAD reads a name as a unit or constant (D9). Raises
    :class:`cpsk_core.CpskLoadError`.
    """
    return _Importer(document, sketch_name, varset_name, is_unit).run()


@dataclass
class _Importer:
    document: Document
    sketch_name: str
    varset_name: str
    is_unit: Callable[[str], bool]
    warnings: list[Diagnostic] = field(default_factory=list)
    errors: list[Diagnostic] = field(default_factory=list)
    compiled: cpsk.Sketch | None = None
    names: dict[str, str] = field(default_factory=dict)  # CPSK id → FreeCAD name
    variables: dict[str, Element] = field(default_factory=dict)  # id → <variable>

    def run(self) -> tuple[SketchData, list[Diagnostic]]:
        root = self.document.root
        for attribute, unit in (("unit-length", "mm"), ("unit-angle", "deg")):
            if (root.get(attribute) or unit) != unit:
                message = f"only {unit} documents can be imported ({attribute}, plan D8)"
                self.errors.append(error(Stage.LOAD, "unit", message, line=root.line))
        if self.errors:
            raise CpskLoadError(self.errors)
        compiled, inactive = self._compile()
        self.compiled = compiled
        container = self.document.container("variables")
        for variable in container.elements("variable") if container is not None else ():
            identifier = variable.get("id")
            if identifier is not None:
                self.variables[identifier] = variable
        self._name_everything(compiled)
        kept = Kept(
            ids={p.index: p.id or "" for p in compiled.primitives},
            names={fc: cpsk for cpsk, fc in self.names.items() if fc != cpsk},
            metadata=self._metadata(),
            varset=self.varset_name if self.variables else None,
            order=[self.names[identifier] for identifier in self.variables],
        )
        data = SketchData(
            name=self.sketch_name,
            label=" ".join(compiled.metadata.get("title", ("",))[0].split()),
            geometry=[_geometry(p) for p in compiled.primitives],
            kept=kept,
        )
        for constraint in compiled.constraints:
            data.constraints.append(
                self._constraint(constraint, id(constraint.element) in inactive)
            )
            formula = self._formula(constraint)
            if formula is not None and constraint.driving:
                name = self._fc_name(constraint, data)
                data.expressions[name] = to_freecad(formula, self._sketch_reference)
        if self.variables:
            data.varsets.append(self._varset(compiled, kept))
        self._check_cycles(compiled)
        if self.errors:
            raise CpskLoadError(self.errors)
        return data, [*compiled.warnings, *self.warnings]

    def _compile(self) -> tuple[cpsk.Sketch, set[int]]:
        """Compile, with the constraints of ``<freecad:inactive>`` moved to the top level."""
        working = copy.deepcopy(self.document)
        inactive: set[int] = set()
        constraints = working.container("constraints")
        if constraints is not None:
            children: list[Node] = []
            for child in constraints.children:
                if _is_inactive(child):
                    assert isinstance(child, Element)
                    moved = [c for c in child.children if isinstance(c, Element)]
                    inactive |= {id(c) for c in moved}
                    children += moved
                    continue
                children.append(child)
            constraints.children = children
        return compile_document(working), inactive

    # ----- Names (D9) -----

    def _name_everything(self, compiled: cpsk.Sketch) -> None:
        """FreeCAD names for every constraint and variable id; renames unit names that need it."""
        needed: set[str] = set()
        for constraint in compiled.constraints:
            formula = self._formula(constraint)
            if formula is not None and constraint.driving:
                needed |= {str(n) for n in names(parse(formula))}
                if constraint.id:
                    needed.add(constraint.id)
        for identifier, variable in self.variables.items():
            formula = variable.get("value") or "0"
            needed |= {str(n) for n in names(parse(formula))}
            if not is_plain_number(formula):
                needed.add(identifier)
        taken = {c.id for c in compiled.constraints if c.id} | set(self.variables)
        for identifier in [*(c.id for c in compiled.constraints if c.id), *self.variables]:
            name = identifier
            if identifier in needed and self.is_unit(identifier):
                name = _free(f"{identifier}_", taken, self.is_unit)
                taken.add(name)
                self.warnings.append(
                    warning(
                        Stage.LOAD,
                        "renamed",
                        f"{identifier!r} is a unit or constant in FreeCAD expressions: imported"
                        f" as {name!r} (export writes {identifier!r} again)",
                        ids=[identifier],
                    )
                )
            self.names[identifier] = name

    def _fc_name(self, constraint: cpsk.Constraint, data: SketchData) -> str:
        """The FreeCAD name of a constraint with a formula; anonymous ones get a generated name."""
        if constraint.id:
            return self.names[constraint.id]
        taken = set(self.names.values()) | set(data.kept.names)
        name = next(f"cpsk_{n}" for n in range(1, len(taken) + 2) if f"cpsk_{n}" not in taken)
        data.kept.names[name] = ""
        data.constraints[-1] = dataclasses.replace(data.constraints[-1], name=name)
        return name

    def _sketch_reference(self, identifier: str) -> str:
        if identifier in self.variables:
            return f"{self.varset_name}.{self.names[identifier]}"
        return f"Constraints.{self.names[identifier]}"

    def _varset_reference(self, identifier: str) -> str:
        if identifier in self.variables:
            return self.names[identifier]
        return f"{self.sketch_name}.Constraints.{self.names[identifier]}"

    # ----- Pieces -----

    def _metadata(self) -> list[tuple[str, str]]:
        container = self.document.container("metadata")
        if container is None:
            return []
        return [(item.name, " ".join(item.text.split())) for item in container.elements()]

    def _formula(self, constraint: cpsk.Constraint) -> str | None:
        """The ``value`` as written, when FreeCAD needs it as an expression."""
        element = constraint.element
        formula = element.get("value") if element is not None else None
        if formula is None or not constraint.driving or is_plain_number(formula):
            return None
        return formula

    def _constraint(self, constraint: cpsk.Constraint, inactive: bool) -> Constraint:
        operands = constraint.operands
        order = {
            "coincident": ("a", "b"),
            "point-on": ("point", "object"),
            "symmetric": ("a", "b", "about"),
        }.get(constraint.type, ("of", "a", "b"))
        chosen = [operands[name] for name in order if name in operands]
        if constraint.type == "distance" and len(chosen) == 2 and chosen[0].kind == "line":
            chosen.reverse()  # FreeCAD: (point, line)
        if constraint.type in ("distance-x", "distance-y") and len(chosen) == 2:
            a, b = chosen
            if a.target == "origin":
                chosen = [b]  # DistanceX on a point
            elif (
                isinstance(a.target, int)
                and a.target == b.target
                and (a.point, b.point) == ("start", "end")
                and self.compiled is not None
                and self.compiled.primitives[a.target].kind == "line"
            ):
                chosen = [_edge(a)]  # DistanceX on a line
        if constraint.type == "angle" and len(chosen) == 2 and chosen[0].target == "x_axis":
            chosen = [chosen[1]]  # Angle on a line
        fields: list[int] = []
        for operand in chosen:
            fields += _geo_pos(operand)
        if constraint.type == "block":
            fields[1] = 0  # Block takes the GeoId only, also for a point
        while len(fields) < 6:
            fields += [UNDEFINED, 0]
        first, first_pos, second, second_pos, third, third_pos = fields
        value = 0.0
        if constraint.type in ("distance", "distance-x", "distance-y", "radius", "diameter"):
            value = self._value(constraint)
        elif constraint.type == "angle":
            value = math.radians(self._value(constraint))
        if constraint.type == "tangent" and chosen[0].kind == "point":
            value = 0.0  # FreeCAD sets the locked direction itself (phase 0)
        return Constraint(
            _TYPES[constraint.type],
            first,
            first_pos,
            second,
            second_pos,
            third,
            third_pos,
            value=value,
            name=self.names.get(constraint.id or "", ""),
            driving=constraint.driving,
            active=not inactive,
        )

    def _value(self, constraint: cpsk.Constraint) -> float:
        if constraint.value is not None:
            return constraint.value
        written = constraint.element.get("value") if constraint.element is not None else None
        try:
            return float(written) if written is not None else 1.0  # FreeCAD measures it
        except ValueError:
            return 1.0

    def _varset(self, compiled: cpsk.Sketch, kept: Kept) -> VarSet:
        variables = []
        for identifier, element in self.variables.items():
            name = self.names[identifier]
            formula = element.get("value") or "0"
            low, high = element.get("min"), element.get("max")
            if low is not None or high is not None:
                kept.limits[name] = (low, high)
            variables.append(
                Variable(
                    name,
                    _PROPERTY_TYPES[element.get("type") or "number"],
                    compiled.variables[identifier],
                    None
                    if is_plain_number(formula)
                    else to_freecad(formula, self._varset_reference),
                    element.get("description") or "",
                )
            )
        return VarSet(self.varset_name, "", tuple(variables))

    def _check_cycles(self, compiled: cpsk.Sketch) -> None:
        """FreeCAD refuses a VarSet that uses the sketch while the sketch uses the VarSet."""
        constraint_ids = {c.id for c in compiled.constraints if c.id}
        uses_constraints = [
            identifier
            for identifier, element in self.variables.items()
            if {str(n) for n in names(parse(element.get("value") or "0"))} & constraint_ids
        ]
        uses_variables = any(
            {str(n) for n in names(parse(formula))} & set(self.variables)
            for c in compiled.constraints
            if (formula := self._formula(c)) is not None
        )
        if uses_constraints and uses_variables:
            for identifier in uses_constraints:
                self.errors.append(
                    error(
                        Stage.LOAD,
                        "unsupported",
                        f"variable {identifier!r} uses a constraint value while constraints use"
                        " variables: FreeCAD rejects the circular dependency between the VarSet"
                        " and the sketch",
                        ids=[identifier],
                        line=self.variables[identifier].line,
                    )
                )


def _is_inactive(node: Node) -> bool:
    """Whether a node is the ``<freecad:inactive>`` wrapper of deactivated constraints (D6)."""
    return isinstance(node, Element) and (node.namespace, node.name) == (
        FREECAD_NAMESPACE,
        "inactive",
    )


def _geometry(primitive: cpsk.Primitive) -> Geometry:
    g = primitive.geometry
    coords: tuple[float, ...]
    if isinstance(g, cpsk.Point):
        coords = (g.x, g.y)
    elif isinstance(g, cpsk.Line):
        coords = (g.x1, g.y1, g.x2, g.y2)
    elif isinstance(g, cpsk.Circle):
        coords = (g.cx, g.cy, g.r)
    else:
        coords = (g.cx, g.cy, g.r, g.start_angle, g.end_angle)
    return Geometry(primitive.kind, coords, primitive.construction)


def _geo_pos(operand: cpsk.Operand) -> list[int]:
    if operand.target == "origin":
        return [-1, 1]
    if operand.target in ("x_axis", "y_axis"):
        return [-1 if operand.target == "x_axis" else -2, 0]
    assert isinstance(operand.target, int)
    if operand.point is None:
        return [operand.target, 1 if operand.kind == "point" else 0]
    return [operand.target, _POSITIONS[operand.point]]


def _edge(operand: cpsk.Operand) -> cpsk.Operand:
    return cpsk.Operand(operand.target, None, "line", str(operand.target))


def _free(base: str, taken: set[str], is_unit: Callable[[str], bool]) -> str:
    """``base`` or ``base<n>``: not taken and not a FreeCAD unit."""
    candidate, n = base, 1
    while candidate in taken or is_unit(candidate):
        n += 1
        candidate = f"{base}{n}"
    return candidate
