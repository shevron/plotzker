"""A plain-data snapshot of a FreeCAD sketch: what the exporter needs, without FreeCAD.

:func:`snapshot` reads a ``Sketcher::SketchObject`` (duck-typed: this module does not import
FreeCAD); the exporter works on the snapshot only, so the mapping can be tested without FreeCAD.
Units are FreeCAD's: lengths in mm, constraint angles in radians, arc angles and VarSet angles
in degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

UNDEFINED = -2000
"""FreeCAD's ``GeoUndef``: an unused constraint operand."""


@dataclass(frozen=True)
class Geometry:
    """A sketch geometry.

    ``kind`` is ``point``, ``line``, ``circle`` or ``arc``, or the FreeCAD type name of an
    unsupported geometry. ``coords``: point (x, y); line (x1, y1, x2, y2); circle (cx, cy, r);
    arc (cx, cy, r, start, end) with angles in degrees, counterclockwise.
    """

    kind: str
    coords: tuple[float, ...] = ()
    construction: bool = False


@dataclass(frozen=True)
class Constraint:
    """A ``Sketcher.Constraint``; positions: 0 edge, 1 start, 2 end, 3 center."""

    type: str
    first: int
    first_pos: int = 0
    second: int = UNDEFINED
    second_pos: int = 0
    third: int = UNDEFINED
    third_pos: int = 0
    value: float = 0.0
    name: str = ""
    driving: bool = True
    active: bool = True


@dataclass(frozen=True)
class Variable:
    """A VarSet property; ``value`` in mm, degrees or as a plain number."""

    name: str
    type: str
    value: float
    expression: str | None = None
    description: str = ""


@dataclass(frozen=True)
class VarSet:
    """An ``App::VarSet`` and its own (user-added) properties."""

    name: str
    label: str
    variables: tuple[Variable, ...] = ()


@dataclass
class SketchData:
    """Everything the exporter reads from a sketch and its document."""

    name: str = "Sketch"
    label: str = "Sketch"
    geometry: list[Geometry] = field(default_factory=list)
    external: list[Geometry] = field(default_factory=list)
    """External geometry; item ``i`` has GeoId ``-3 - i``."""
    constraints: list[Constraint] = field(default_factory=list)
    expressions: dict[str, str] = field(default_factory=dict)
    """Constraint name → FreeCAD expression."""
    varsets: list[VarSet] = field(default_factory=list)
    """Every VarSet in the document."""
    dof: int | None = None
    conflicting: list[int] = field(default_factory=list)
    """FreeCAD's constraint numbers (1-based), as the sketch reports them."""
    redundant: list[int] = field(default_factory=list)
    malformed: list[int] = field(default_factory=list)


_VARSET_BUILTINS = frozenset({"ExpressionEngine", "Label", "Label2", "Visibility"})
_CONSTRAINT_PREFIX = ".Constraints."


def snapshot(sketch: Any) -> SketchData:
    """Read a ``Sketcher::SketchObject``; solves it first so its status is current."""
    sketch.solve()
    return SketchData(
        name=sketch.Name,
        label=sketch.Label,
        geometry=[_geometry(g, sketch.getConstruction(i)) for i, g in enumerate(sketch.Geometry)],
        external=[_geometry(g, True) for g in sketch.ExternalGeo[2:]],  # [0], [1]: the axes
        constraints=[
            Constraint(
                c.Type,
                c.First,
                c.FirstPos,
                c.Second,
                c.SecondPos,
                c.Third,
                c.ThirdPos,
                c.Value,
                c.Name,
                c.Driving,
                c.IsActive,
            )
            for c in sketch.Constraints
        ],
        expressions={
            path[len(_CONSTRAINT_PREFIX) :]: text
            for path, text in sketch.ExpressionEngine
            if path.startswith(_CONSTRAINT_PREFIX)
        },
        varsets=[_varset(o) for o in sketch.Document.Objects if o.TypeId == "App::VarSet"],
        dof=_dof(sketch),
        conflicting=list(sketch.ConflictingConstraints),
        redundant=list(sketch.RedundantConstraints),
        malformed=list(sketch.MalformedConstraints),
    )


def _dof(sketch: Any) -> int | None:
    dof = getattr(sketch, "DoF", None)
    return int(dof) if dof is not None else None


def _geometry(geometry: Any, construction: bool) -> Geometry:
    kind = type(geometry).__name__
    if kind == "Point":
        return Geometry("point", (geometry.X, geometry.Y), construction)
    if kind == "LineSegment":
        start, end = geometry.StartPoint, geometry.EndPoint
        return Geometry("line", (start.x, start.y, end.x, end.y), construction)
    if kind == "Circle":
        return Geometry("circle", _circle(geometry), construction)
    if kind == "ArcOfCircle" and geometry.Axis.z > 0:
        angles = (math.degrees(geometry.FirstParameter), math.degrees(geometry.LastParameter))
        return Geometry("arc", (*_circle(geometry), *angles), construction)
    if kind == "ArcOfCircle":
        kind = "ArcOfCircle (clockwise)"
    return Geometry(kind, (), construction)


def _circle(geometry: Any) -> tuple[float, float, float]:
    return (geometry.Center.x, geometry.Center.y, geometry.Radius)


def _varset(varset: Any) -> VarSet:
    expressions = dict(varset.ExpressionEngine)
    variables = []
    for name in varset.PropertiesList:
        if name in _VARSET_BUILTINS:
            continue
        value = getattr(varset, name)
        value = getattr(value, "Value", value)
        variables.append(
            Variable(
                name,
                varset.getTypeIdOfProperty(name),
                float(value) if isinstance(value, int | float) else math.nan,
                expressions.get(name),
                varset.getDocumentationOfProperty(name),
            )
        )
    return VarSet(varset.Name, varset.Label, tuple(variables))
