"""A plain-data snapshot of a FreeCAD sketch: what the exporter needs, without FreeCAD.

:func:`snapshot` reads a ``Sketcher::SketchObject`` (duck-typed: this module does not import
FreeCAD); the exporter works on the snapshot only, so the mapping can be tested without FreeCAD.
Units are FreeCAD's: lengths in mm, constraint angles in radians, arc angles and VarSet angles
in degrees.
"""

from __future__ import annotations

import json
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


KEPT_PROPERTY = "CpskData"
"""The hidden sketch property that holds :class:`Kept` as JSON."""


@dataclass
class Kept:
    """What an import keeps on the sketch so that export writes the file back (D4, D9).

    Stored as JSON in the sketch's hidden ``CpskData`` property; geometry is keyed by FreeCAD's
    GeometryId there, which survives deleting and adding geometry.
    """

    ids: dict[int, str] = field(default_factory=dict)
    """Geometry index → CPSK primitive id; ``""``: the primitive had no id in the file."""
    names: dict[str, str] = field(default_factory=dict)
    """FreeCAD constraint or variable name → CPSK id, where they differ (D9 renames, and
    generated names of anonymous constraints with a formula, mapped to ``""``)."""
    limits: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)
    """Variable (FreeCAD name) → its ``min`` and ``max`` as written."""
    metadata: list[tuple[str, str]] = field(default_factory=list)
    """The metadata elements and their text; ``title`` follows the sketch label on export."""
    varset: str | None = None
    """The name of the VarSet the import created; exported even if no expression uses it."""
    order: list[str] = field(default_factory=list)
    """That VarSet's variables (FreeCAD names) in document order; FreeCAD sorts properties."""

    def to_json(self, geometry_ids: list[int]) -> str:
        """JSON, with geometry indexes turned into GeometryIds (``geometry_ids[index]``)."""
        return json.dumps(
            {
                "version": 1,
                "ids": {str(geometry_ids[i]): id for i, id in self.ids.items()},
                "names": self.names,
                "limits": {name: list(pair) for name, pair in self.limits.items()},
                "metadata": [list(item) for item in self.metadata],
                "varset": self.varset,
                "order": self.order,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, text: str, geometry_ids: list[int]) -> Kept:
        """Read :meth:`to_json` output; ids of geometry that no longer exists are dropped."""
        data = json.loads(text)
        index = {geometry_id: i for i, geometry_id in enumerate(geometry_ids)}
        return cls(
            ids={index[int(k)]: v for k, v in data["ids"].items() if int(k) in index},
            names=dict(data["names"]),
            limits={name: (pair[0], pair[1]) for name, pair in data["limits"].items()},
            metadata=[(name, text) for name, text in data["metadata"]],
            varset=data["varset"],
            order=list(data.get("order", [])),
        )


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
    kept: Kept = field(default_factory=Kept)


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
        kept=_kept(sketch),
    )


def _kept(sketch: Any) -> Kept:
    text = getattr(sketch, KEPT_PROPERTY, "")
    if not text:
        return Kept()
    return Kept.from_json(text, [sketch.getGeometryId(i) for i in range(len(sketch.Geometry))])


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
