"""Regions of a part, used to place loads, supports and displacement limits.

A region is a geometric selector in the part's analysis frame (``Part.frame``). Loads and
supports act on the **surface faces** whose centroid lies in the region (and, if ``facing`` is
set, whose outward normal points within ``facing_tol_deg`` of that direction). Displacement
limits look at the **mesh nodes** inside the region.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from cadder.geometry import FN_HOLE
from cadder.types import Vec3

if TYPE_CHECKING:
    from pythonscad import Solid

_AXES: dict[Vec3, tuple[float, float, float]] = {
    (1.0, 0.0, 0.0): (0, 90, 0),
    (0.0, 1.0, 0.0): (-90, 0, 0),
    (0.0, 0.0, 1.0): (0, 0, 0),
}


def _unit(v: Sequence[float]) -> Vec3:
    """``v`` scaled to length 1."""
    n = math.sqrt(sum(c * c for c in v))
    if n == 0:
        raise ValueError("zero-length direction")
    return v[0] / n, v[1] / n, v[2] / n


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    """Dot product."""
    return sum(x * y for x, y in zip(a, b, strict=True))


def _faces_toward(facing: Vec3 | None, tol_deg: float, normal: Sequence[float] | None) -> bool:
    """Whether a face normal passes a region's ``facing`` filter."""
    if facing is None or normal is None:
        return True
    return _dot(_unit(normal), _unit(facing)) >= math.cos(math.radians(tol_deg))


@dataclass(frozen=True)
class Box:
    """An axis-aligned box from ``lo`` to ``hi`` (mm)."""

    lo: Vec3
    hi: Vec3
    facing: Vec3 | None = None  #: only faces whose outward normal points this way
    facing_tol_deg: float = 45.0

    def contains(self, p: Sequence[float]) -> bool:
        """Whether point ``p`` lies in the box."""
        return all(self.lo[i] <= p[i] <= self.hi[i] for i in range(3))

    def matches(self, centroid: Sequence[float], normal: Sequence[float] | None = None) -> bool:
        """Whether a face with this centroid and outward normal belongs to the region."""
        return self.contains(centroid) and _faces_toward(self.facing, self.facing_tol_deg, normal)

    def bounds(self) -> tuple[Vec3, Vec3]:
        """Axis-aligned bounding box of the region."""
        return self.lo, self.hi

    def solid(self) -> Solid:
        """The region as a solid, for checking that it touches the part."""
        size = [self.hi[i] - self.lo[i] for i in range(3)]
        return cube(size).translate(list(self.lo))


@dataclass(frozen=True)
class Cylinder:
    """A cylinder or ring (``inner_radius`` > 0) about ``axis`` through ``center`` (mm)."""

    center: Vec3
    axis: Vec3  #: x, y or z unit vector
    radius: float
    half_length: float
    inner_radius: float = 0.0
    facing: Vec3 | None = None
    facing_tol_deg: float = 45.0

    def __post_init__(self) -> None:
        """Check the axis and radii."""
        if self.axis not in _AXES:
            raise ValueError(f"axis must be (1, 0, 0), (0, 1, 0) or (0, 0, 1), got {self.axis}")
        if not 0 <= self.inner_radius < self.radius or self.half_length <= 0:
            raise ValueError("need 0 <= inner_radius < radius and half_length > 0")

    def contains(self, p: Sequence[float]) -> bool:
        """Whether point ``p`` lies in the cylinder (or ring)."""
        rel = [p[i] - self.center[i] for i in range(3)]
        along = _dot(rel, self.axis)
        radial = math.sqrt(max(0.0, _dot(rel, rel) - along * along))
        return abs(along) <= self.half_length and self.inner_radius <= radial <= self.radius

    def matches(self, centroid: Sequence[float], normal: Sequence[float] | None = None) -> bool:
        """Whether a face with this centroid and outward normal belongs to the region."""
        return self.contains(centroid) and _faces_toward(self.facing, self.facing_tol_deg, normal)

    def bounds(self) -> tuple[Vec3, Vec3]:
        """Axis-aligned bounding box of the region."""
        reach = [self.half_length if self.axis[i] else self.radius for i in range(3)]
        lo = (self.center[0] - reach[0], self.center[1] - reach[1], self.center[2] - reach[2])
        hi = (self.center[0] + reach[0], self.center[1] + reach[1], self.center[2] + reach[2])
        return lo, hi

    def solid(self) -> Solid:
        """The region as a solid, for checking that it touches the part."""
        length = 2 * self.half_length
        body = cylinder(d=2 * self.radius, h=length, fn=FN_HOLE)
        if self.inner_radius > 0:
            body = body - cylinder(d=2 * self.inner_radius, h=length + 2, fn=FN_HOLE).translate(
                [0, 0, -1]
            )
        return (
            body.translate([0, 0, -self.half_length])
            .rotate(list(_AXES[self.axis]))
            .translate(list(self.center))
        )


Region = Box | Cylinder


def select_faces(
    region: Region, points: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]
) -> list[int]:
    """Indices of the mesh faces that belong to ``region`` (centroid and normal tests)."""
    selected = []
    for index, face in enumerate(faces):
        corners = [points[v] for v in face]
        centroid = [sum(c[i] for c in corners) / len(corners) for i in range(3)]
        normal = _newell(corners)
        if region.matches(centroid, normal):
            selected.append(index)
    return selected


def _newell(corners: Sequence[Sequence[float]]) -> list[float] | None:
    """Normal of a planar polygon (Newell's method); ``None`` if it has no area."""
    n = [0.0, 0.0, 0.0]
    for (x1, y1, z1), (x2, y2, z2) in zip(corners, [*corners[1:], corners[0]], strict=True):
        n[0] += (y1 - y2) * (z1 + z2)
        n[1] += (z1 - z2) * (x1 + x2)
        n[2] += (x1 - x2) * (y1 + y2)
    return n if any(n) else None


@dataclass(frozen=True)
class Placement:
    """Where a part-local frame sits in the part's frame: quarter turns about z, then a shift.

    Lets one description (the tensioner's) serve parts that mount it in different directions.
    """

    quarter_turns: int = 0
    offset: Vec3 = (0.0, 0.0, 0.0)

    def vector(self, v: Sequence[float]) -> Vec3:
        """A direction or free vector (no shift)."""
        x, y, z = v
        for _ in range(self.quarter_turns % 4):
            x, y = -y, x
        return x, y, z

    def point(self, p: Sequence[float]) -> Vec3:
        """A position."""
        x, y, z = self.vector(p)
        return x + self.offset[0], y + self.offset[1], z + self.offset[2]

    def region(self, region: Region) -> Region:
        """The region in the part's frame."""
        facing = None if region.facing is None else self.vector(region.facing)
        if isinstance(region, Box):
            a, b = self.point(region.lo), self.point(region.hi)
            lo = (min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]))
            hi = (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2]))
            return Box(lo, hi, facing, region.facing_tol_deg)
        axis = self.vector(region.axis)
        return Cylinder(
            self.point(region.center),
            (abs(round(axis[0])) * 1.0, abs(round(axis[1])) * 1.0, abs(round(axis[2])) * 1.0),
            region.radius,
            region.half_length,
            region.inner_radius,
            facing,
            region.facing_tol_deg,
        )


#: DESIGN: radius of the friction zone around a clamping screw (about twice the head diameter):
#: the foot's underside there is taken as bonded to what it is clamped on.
BOND_RADIUS = 8.0


def bond_zone(centre: Vec3, radius: float = BOND_RADIUS) -> Cylinder:
    """The underside of a foot (facing down) within ``radius`` of a clamping screw at ``centre``
    (x, y and the z of the underside)."""
    return Cylinder(centre, (0, 0, 1), radius, 0.3, facing=(0, 0, -1))
