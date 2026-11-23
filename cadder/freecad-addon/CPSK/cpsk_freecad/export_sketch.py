"""FreeCAD sketch → CPSK document (plugin plan §4).

:func:`to_document` maps a :class:`~cpsk_freecad.sketch_data.SketchData` snapshot, so it runs
without FreeCAD; :func:`export_sketch` snapshots a live sketch and writes the file.

- Primitive ids come from FreeCAD's GeoIds: ``point<n>`` for points, ``edge<n>`` for curves
  (``n`` = GeoId + 1, FreeCAD's ``Edge<n>``), ``external<n>`` for external geometry (GeoId
  ``-2 - n``), which is written as construction geometry with a nested ``<block/>`` (R2).
- Constraints follow plan §4.2 and are placed canonically (spec §11.4). FreeCAD names become
  constraint ids; names that are not valid CPSK identifiers are refused (D5).
- Expressions are translated (:mod:`cpsk_freecad.expressions`); variables come from the VarSets
  the expressions reference (D2), with all their properties.
- Deactivated constraints (D6) are kept inside a ``<freecad:inactive>`` extension element at the
  top level, so CPSK readers ignore them and the importer can restore them.
- Anything CPSK 0.1 cannot represent is refused: :class:`cpsk_core.CpskExportError` lists every
  problem (R4). Sketch problems FreeCAD reports (degrees of freedom, conflicting, redundant or
  malformed constraints) are returned as warnings.

The document is written in millimetres and degrees (D8).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path as FilePath
from typing import Any

from cpsk_core import (
    RESERVED,
    CpskError,
    CpskExportError,
    Diagnostic,
    Document,
    Element,
    Stage,
    compile_document,
    element,
    format_number,
    nest_constraints,
)
from cpsk_core.document import save
from cpsk_core.errors import error, warning
from cpsk_core.formula import IDENTIFIER_RE
from cpsk_freecad.expressions import Path, UnsupportedExpressionError, translate
from cpsk_freecad.sketch_data import UNDEFINED, Constraint, SketchData, VarSet, snapshot

FREECAD_NAMESPACE = "https://github.com/shevron/plotzker/ns/cpsk-freecad"
"""Extension namespace for FreeCAD-only state (spec §11.3, plan D6)."""
FREECAD_PREFIX = "freecad"

_DIMENSIONAL = frozenset({"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"})
_POSITIONS = {
    "line": {1: "start", 2: "end"},
    "circle": {3: "center"},
    "arc": {1: "start", 2: "end", 3: "center"},
}
_VARIABLE_TYPES = {
    "App::PropertyLength": "length",
    "App::PropertyDistance": "length",
    "App::PropertyAngle": "angle",
    "App::PropertyFloat": "number",
    "App::PropertyInteger": "number",
}
_TYPES = frozenset(
    {"Coincident", "PointOnObject", "Horizontal", "Vertical", "Parallel", "Perpendicular"}
    | {"Tangent", "Equal", "Symmetric", "Block"}
    | _DIMENSIONAL
)
"""FreeCAD constraint types with a CPSK equivalent (in some forms, see ``_map``)."""
_CURVES = frozenset({"line", "circle", "arc"})
_ROUND = frozenset({"circle", "arc"})
_ROUND_PAIRS = [[a, b] for a in sorted(_ROUND) for b in sorted(_ROUND)]


def export_sketch(sketch: Any, path: str | FilePath) -> list[Diagnostic]:
    """Write a FreeCAD sketch as a CPSK file; returns the warnings.

    Raises :class:`cpsk_core.CpskExportError` listing every unsupported feature; no file is
    written then.
    """
    document, warnings = to_document(snapshot(sketch))
    save(document, path)
    return warnings


def to_document(data: SketchData) -> tuple[Document, list[Diagnostic]]:
    """The CPSK document for a sketch snapshot, and the warnings; see the module docstring."""
    return _Exporter(data).run()


class _UnsupportedError(Exception):
    pass


@dataclass(frozen=True)
class _Operand:
    reference: str
    kind: str  # "point" or a curve kind


class _Exporter:
    def __init__(self, data: SketchData) -> None:
        self.data = data
        self.problems: list[Diagnostic] = []
        self.primitives: dict[int, tuple[str, str]] = {}  # GeoId → (id, kind)
        self.names = {c.name for c in data.constraints if c.name}
        self.varsets: list[VarSet] = []  # referenced, in discovery order
        self.variable_names: dict[str, str] = {}  # variable → VarSet name

    def run(self) -> tuple[Document, list[Diagnostic]]:
        document = Document.new(unit_length="mm", unit_angle="deg")
        document.prefixes[FREECAD_NAMESPACE] = FREECAD_PREFIX
        if self.data.label:
            metadata = document.container("metadata", create=True)
            assert metadata is not None
            metadata.append(_text("title", self.data.label))
        geometry = self._geometry()
        constraints, inactive = self._constraints()
        variables = self._variables()
        if self.problems:
            raise CpskExportError(self.problems)
        for container, children in (
            ("variables", variables),
            ("geometry", geometry),
            ("constraints", constraints),
        ):
            if children:
                parent = document.container(container, create=True)
                assert parent is not None
                parent.children += children
        nest_constraints(document)
        if inactive:
            wrapper = Element("inactive", namespace=FREECAD_NAMESPACE)
            wrapper.children += inactive
            parent = document.container("constraints", create=True)
            assert parent is not None
            parent.append(wrapper)
        try:
            compile_document(document)
        except CpskError as e:  # a mapping gap: report it rather than write a broken file
            raise CpskExportError(e.diagnostics) from None
        return document, self._warnings()

    # ----- Geometry -----

    def _geometry(self) -> list[Element]:
        primitives = []
        for index, geometry in enumerate(self.data.geometry):
            prefix = "point" if geometry.kind == "point" else "edge"
            created = self._primitive(index, f"{prefix}{index + 1}", geometry)
            if created is not None:
                primitives.append(created)
        for index, geometry in enumerate(self.data.external):
            created = self._primitive(-3 - index, f"external{index + 1}", geometry)
            if created is not None:
                created.set("construction", "true")
                created.append(element("block"))
                primitives.append(created)
        return primitives

    def _primitive(self, geo_id: int, identifier: str, geometry: Any) -> Element | None:
        names = {
            "point": ("x", "y"),
            "line": ("x1", "y1", "x2", "y2"),
            "circle": ("cx", "cy", "r"),
            "arc": ("cx", "cy", "r", "start_angle", "end_angle"),
        }.get(geometry.kind)
        if names is None:
            self._problem(f"{identifier}: {geometry.kind} geometry is not supported", identifier)
            return None
        self.primitives[geo_id] = (identifier, geometry.kind)
        attrs: dict[str, str | float | bool | None] = {"id": identifier}
        if geometry.construction:
            attrs["construction"] = True
        attrs.update(zip(names, geometry.coords, strict=True))
        return element(geometry.kind, **attrs)

    # ----- Constraints -----

    def _constraints(self) -> tuple[list[Element], list[Element]]:
        active: list[Element] = []
        inactive: list[Element] = []
        for index, constraint in enumerate(self.data.constraints):
            label = _label(index, constraint)
            try:
                created = self._constraint(constraint)
            except (_UnsupportedError, UnsupportedExpressionError) as e:
                self._problem(f"{label}: {constraint.type}: {e}", label)
                continue
            (active if constraint.active else inactive).append(created)
        return active, inactive

    def _constraint(self, constraint: Constraint) -> Element:
        if constraint.name and (
            not IDENTIFIER_RE.fullmatch(constraint.name) or constraint.name in RESERVED
        ):
            raise _UnsupportedError(
                f"the name {constraint.name!r} is not a valid CPSK identifier (spec §3)"
            )
        name, operands = self._map(constraint)
        attrs: dict[str, str | float | bool | None] = {"id": constraint.name or None}
        attrs.update(operands)
        if constraint.type in _DIMENSIONAL:
            if not constraint.driving:
                attrs["driving"] = False
            attrs["value"] = self._value(constraint)
        return element(name, **attrs)

    def _value(self, constraint: Constraint) -> str:
        expression = self.data.expressions.get(constraint.name) if constraint.driving else None
        if expression is not None:
            return translate(expression, self._sketch_resolver)
        if constraint.type == "Angle":  # radians; 12 digits turn 29.999999999999996 into 30
            return format_number(float(f"{math.degrees(constraint.value):.12g}"))
        return format_number(constraint.value)

    def _map(self, c: Constraint) -> tuple[str, dict[str, str | float | bool | None]]:
        if c.type not in _TYPES:
            raise _UnsupportedError("CPSK 0.1 has no such constraint")
        operands = [
            (geo, pos)
            for geo, pos in (
                (c.first, c.first_pos),
                (c.second, c.second_pos),
                (c.third, c.third_pos),
            )
            if geo != UNDEFINED
        ]
        refs = [self._operand(geo, pos) for geo, pos in operands]
        kinds = [r.kind for r in refs]  # "point" for a point or a point of a curve, else an edge
        t = c.type

        def named(*names: str) -> dict[str, str | float | bool | None]:
            return dict(zip(names, (r.reference for r in refs), strict=True))

        if t == "Coincident" and kinds == ["point", "point"]:
            return "coincident", named("a", "b")
        if t == "PointOnObject" and len(kinds) == 2 and kinds[0] == "point" and kinds[1] in _CURVES:
            return "point-on", named("point", "object")
        if t in ("Horizontal", "Vertical") and kinds == ["line"]:
            return t.lower(), named("of")
        if t in ("Horizontal", "Vertical") and kinds == ["point", "point"]:
            return t.lower(), named("a", "b")
        if t in ("Parallel", "Perpendicular") and kinds == ["line", "line"]:
            return t.lower(), named("a", "b")
        if t == "Tangent" and len(kinds) == 2 and set(kinds) <= _CURVES and kinds != ["line"] * 2:
            return "tangent", named("a", "b")
        if t == "Tangent" and kinds == ["point", "point"] and self._end_points(operands):
            return "tangent", named("a", "b")
        if t == "Equal" and kinds in (["line", "line"], *_ROUND_PAIRS):
            return "equal", named("a", "b")
        if (
            t == "Symmetric"
            and kinds[:2] == ["point", "point"]
            and kinds[2:] in (["line"], ["point"])
        ):
            return "symmetric", named("a", "b", "about")
        if t == "Block" and len(kinds) == 1 and operands[0][1] == 0:
            return "block", named("of")
        if t == "Distance" and kinds == ["line"]:
            return "distance", named("of")
        if t == "Distance" and kinds in (["point", "point"], ["point", "line"]):
            return "distance", named("a", "b")
        if t in ("DistanceX", "DistanceY"):
            name = "distance-x" if t == "DistanceX" else "distance-y"
            if kinds == ["line"]:
                line = refs[0].reference
                return name, {"a": f"{line}.start", "b": f"{line}.end"}
            if kinds == ["point"]:
                return name, {"a": "origin", "b": refs[0].reference}
            if kinds == ["point", "point"]:
                return name, named("a", "b")
        if t in ("Radius", "Diameter") and len(kinds) == 1 and kinds[0] in _ROUND:
            return t.lower(), named("of")
        if t == "Angle" and kinds == ["line"]:
            return "angle", {"a": "x_axis", "b": refs[0].reference}
        if t == "Angle" and kinds == ["arc"]:
            return "angle", named("of")
        if t == "Angle" and kinds == ["line", "line"]:
            return "angle", named("a", "b")
        raise _UnsupportedError(f"this form ({', '.join(kinds)}) is not supported in CPSK 0.1")

    def _end_points(self, operands: list[tuple[int, int]]) -> bool:
        """Whether every operand is the start or end point of a line or an arc."""
        return all(
            pos in (1, 2) and geo in self.primitives and self.primitives[geo][1] in ("line", "arc")
            for geo, pos in operands
        )

    def _operand(self, geo: int, pos: int) -> _Operand:
        if geo == -1 and pos == 1:
            return _Operand("origin", "point")
        if geo in (-1, -2) and pos == 0:
            return _Operand("x_axis" if geo == -1 else "y_axis", "line")
        if geo not in self.primitives:
            raise _UnsupportedError(f"it references unsupported geometry (GeoId {geo})")
        identifier, kind = self.primitives[geo]
        if pos == 0:
            return _Operand(identifier, kind)
        if kind == "point" and pos == 1:
            return _Operand(identifier, "point")
        point = _POSITIONS.get(kind, {}).get(pos)
        if point is None:
            raise _UnsupportedError(f"position {pos} of a {kind} is not supported")
        return _Operand(f"{identifier}.{point}", "point")

    # ----- Expressions and variables -----

    def _sketch_resolver(self, path: Path) -> str:
        parts = path.parts
        if parts[0] == "" or self._is_sketch(path):
            if len(parts) == 3 and parts[1] == "Constraints":
                return self._constraint_reference(parts[2])
            raise UnsupportedExpressionError(f"reference {path} is not supported")
        return self._varset_reference(path)

    def _varset_resolver(self, owner: VarSet) -> Callable[[Path], str]:
        def resolve(path: Path) -> str:
            if path.parts[0] == "" and len(path.parts) == 2:
                return self._variable(owner, path.parts[1], path)
            if self._is_sketch(path) and len(path.parts) == 3 and path.parts[1] == "Constraints":
                return self._constraint_reference(path.parts[2])
            return self._varset_reference(path)

        return resolve

    def _is_sketch(self, path: Path) -> bool:
        return path.parts[0] == (self.data.label if path.label else self.data.name)

    def _constraint_reference(self, name: str) -> str:
        for constraint in self.data.constraints:
            if constraint.name == name:
                if not constraint.driving:
                    raise UnsupportedExpressionError(f"{name!r} is a reference constraint")
                if not constraint.active:
                    raise UnsupportedExpressionError(f"{name!r} is deactivated")
                return name
        raise UnsupportedExpressionError(f"there is no constraint {name!r}")

    def _varset_reference(self, path: Path) -> str:
        if len(path.parts) == 2:
            for varset in self.data.varsets:
                if path.parts[0] == (varset.label if path.label else varset.name):
                    return self._variable(varset, path.parts[1], path)
        raise UnsupportedExpressionError(f"reference {path} is not supported")

    def _variable(self, varset: VarSet, name: str, path: Path) -> str:
        if not any(v.name == name for v in varset.variables):
            raise UnsupportedExpressionError(f"reference {path}: no such VarSet property")
        if varset not in self.varsets:
            self.varsets.append(varset)
        return name

    def _variables(self) -> list[Element]:
        created: list[Element] = []
        index = 0
        while index < len(self.varsets):  # translating may reference more VarSets
            varset = self.varsets[index]
            index += 1
            for variable in varset.variables:
                label = f"{varset.label}.{variable.name}"
                owner = self.variable_names.setdefault(variable.name, varset.name)
                problem = None
                if owner != varset.name:
                    problem = f"another referenced VarSet ({owner}) has a property of that name"
                elif variable.name in self.names:
                    problem = "a sketch constraint has the same name"
                elif not IDENTIFIER_RE.fullmatch(variable.name) or variable.name in RESERVED:
                    problem = "the name is not a valid CPSK identifier (spec §3)"
                elif variable.type not in _VARIABLE_TYPES:
                    problem = f"property type {variable.type} is not supported"
                if problem is None:
                    try:
                        created.append(self._variable_element(varset, variable))
                    except UnsupportedExpressionError as e:
                        problem = str(e)
                if problem is not None:
                    self._problem(f"variable {label}: {problem}", label)
        return created

    def _variable_element(self, varset: VarSet, variable: Any) -> Element:
        if variable.expression is not None:
            value = translate(variable.expression, self._varset_resolver(varset))
        else:
            value = format_number(variable.value)
        return element(
            "variable",
            id=variable.name,
            type=_VARIABLE_TYPES[variable.type],
            value=value,
            description=variable.description or None,
        )

    # ----- Reporting -----

    def _problem(self, message: str, label: str) -> None:
        self.problems.append(error(Stage.EXPORT, "unsupported", message, ids=[label]))

    def _warnings(self) -> list[Diagnostic]:
        data = self.data
        found = []
        if data.dof:
            found.append(
                warning(
                    Stage.EXPORT,
                    "degrees-of-freedom",
                    f"the sketch has {data.dof} remaining degrees of freedom",
                )
            )
        for code, numbers in (
            ("conflicting", data.conflicting),
            ("redundant", data.redundant),
            ("malformed", data.malformed),
        ):
            if numbers:
                labels = [_label(n - 1, data.constraints[n - 1]) for n in numbers]
                found.append(
                    warning(
                        Stage.EXPORT,
                        code,
                        f"{code} constraints: {', '.join(labels)}",
                        ids=labels,
                    )
                )
        return found


def _label(index: int, constraint: Constraint) -> str:
    """How FreeCAD shows a constraint: its name, or ``Constraint<n>``."""
    return constraint.name or f"Constraint{index + 1}"


def _text(name: str, text: str) -> Element:
    created = element(name)
    created.text = text
    return created
