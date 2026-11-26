"""The compiled model of a CPSK sketch: primitives, operands, constraints, evaluated values."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypeAlias

from cpsk_core.errors import Diagnostic
from cpsk_core.formula import Units

if TYPE_CHECKING:
    from cpsk_core.document import Document, Element

Kind: TypeAlias = Literal["point", "line", "circle", "arc"]
Implicit: TypeAlias = Literal["origin", "x_axis", "y_axis"]
PointName: TypeAlias = Literal["start", "end", "center"]

IMPLICIT: dict[Implicit, Kind] = {"origin": "point", "x_axis": "line", "y_axis": "line"}


@dataclass(frozen=True)
class Point:
    """A point."""

    x: float
    y: float

    @property
    def coordinates(self) -> tuple[float, ...]:
        """The numbers that define it, in the order of the constructor."""
        return self.x, self.y


@dataclass(frozen=True)
class Line:
    """A segment from (``x1``, ``y1``) to (``x2``, ``y2``)."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def coordinates(self) -> tuple[float, ...]:
        """The numbers that define it, in the order of the constructor."""
        return self.x1, self.y1, self.x2, self.y2

    @property
    def start(self) -> Point:
        """The start point."""
        return Point(self.x1, self.y1)

    @property
    def end(self) -> Point:
        """The end point."""
        return Point(self.x2, self.y2)


@dataclass(frozen=True)
class Circle:
    """A circle."""

    cx: float
    cy: float
    r: float

    @property
    def coordinates(self) -> tuple[float, ...]:
        """The numbers that define it, in the order of the constructor."""
        return self.cx, self.cy, self.r

    @property
    def center(self) -> Point:
        """The center."""
        return Point(self.cx, self.cy)


@dataclass(frozen=True)
class Arc:
    """A counterclockwise arc; angles in the document angle unit."""

    cx: float
    cy: float
    r: float
    start_angle: float
    end_angle: float
    units: Units = field(default=Units(), compare=False, repr=False)

    @property
    def coordinates(self) -> tuple[float, ...]:
        """The numbers that define it, in the order of the constructor."""
        return self.cx, self.cy, self.r, self.start_angle, self.end_angle

    @property
    def center(self) -> Point:
        """The center."""
        return Point(self.cx, self.cy)

    @property
    def sweep(self) -> float:
        """The sweep in radians, in (0, 2π]."""
        sweep = (self.units.to_radians(self.end_angle - self.start_angle)) % math.tau
        return sweep or math.tau

    def _at(self, angle: float) -> Point:
        a = self.units.to_radians(angle)
        return Point(self.cx + self.r * math.cos(a), self.cy + self.r * math.sin(a))

    @property
    def start(self) -> Point:
        """The start point."""
        return self._at(self.start_angle)

    @property
    def end(self) -> Point:
        """The end point."""
        return self._at(self.end_angle)


Geometry: TypeAlias = Point | Line | Circle | Arc

KINDS: dict[type[Geometry], Kind] = {Point: "point", Line: "line", Circle: "circle", Arc: "arc"}
POINTS: dict[Kind, tuple[PointName, ...]] = {
    "point": (),
    "line": ("start", "end"),
    "circle": ("center",),
    "arc": ("start", "end", "center"),
}


@dataclass(frozen=True)
class Primitive:
    """A geometry element of the sketch, in document order (``index``)."""

    index: int
    id: str | None
    geometry: Geometry
    construction: bool = False
    line: int | None = None

    @property
    def kind(self) -> Kind:
        """``point``, ``line``, ``circle`` or ``arc``."""
        return KINDS[type(self.geometry)]

    @property
    def label(self) -> str:
        """How messages name the primitive."""
        name = f"'{self.id}'" if self.id else "(anonymous)"
        where = f" at line {self.line}" if self.line is not None else ""
        return f"{self.kind} {name}{where}"


@dataclass(frozen=True)
class Operand:
    """A resolved reference: a primitive or an implicit reference, or a point on it."""

    target: int | Implicit
    point: PointName | None
    kind: Kind
    text: str

    @property
    def is_point(self) -> bool:
        """Whether this is a point (a point primitive, a point on a curve, or ``origin``)."""
        return self.kind == "point"


@dataclass(frozen=True)
class Constraint:
    """A constraint, normalized to its top-level form (spec §9.4 rule 5)."""

    type: str
    operands: Mapping[str, Operand]
    value: float | None = None
    driving: bool = True
    id: str | None = None
    line: int | None = None
    parent: int | None = None
    element: Element | None = field(default=None, compare=False, repr=False)
    """The source element (its ``value`` keeps the formula as written); ``None`` if built."""

    @property
    def label(self) -> str:
        """How messages name the constraint."""
        name = f" '{self.id}'" if self.id else ""
        where = f" at line {self.line}" if self.line is not None else ""
        return f"<{self.type}>{name}{where}"


@dataclass(frozen=True)
class Sketch:
    """A loaded and validated CPSK document, with formulas evaluated."""

    version: str
    units: Units
    metadata: Mapping[str, tuple[str, ...]]
    variables: Mapping[str, float]
    primitives: tuple[Primitive, ...]
    constraints: tuple[Constraint, ...]
    warnings: tuple[Diagnostic, ...] = ()
    document: Document | None = field(default=None, compare=False, repr=False)
    """The document the sketch was compiled from."""

    def primitive(self, id: str) -> Primitive:
        """The primitive with this identifier."""
        for primitive in self.primitives:
            if primitive.id == id:
                return primitive
        raise KeyError(id)
