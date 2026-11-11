"""Rendering settings and small geometry helpers shared by all parts.

Units: millimeters and degrees throughout.
"""

import math
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pythonscad import circle, cube, linear_extrude, osimport, square

if TYPE_CHECKING:
    from pythonscad import Solid

#: Facets for round features (OpenSCAD ``$fn``) in rendered output.
FN = 64
#: Facets for holes. Kept separate so holes can be tuned independently.
FN_HOLE = 64
#: Overlap used to keep boolean operations clean (no coplanar faces).
EPS = 0.01

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]


def cos_deg(angle: float) -> float:
    """Cosine of an angle given in degrees (OpenSCAD's ``cos``)."""
    return math.cos(math.radians(angle))


def vadd(a: Sequence[float], b: Sequence[float]) -> tuple[float, ...]:
    """Element-wise sum of two vectors."""
    return tuple(x + y for x, y in zip(a, b, strict=True))


def box(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> Solid:
    """Axis-aligned box between two corners ``(x0, y0, z0)`` and ``(x1, y1, z1)``."""
    return cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def load_sketch(path: str | Path, fn: int | None = None) -> Solid:
    """Load a 2D sketch drawn as an SVG file; returns a 2D object ready to extrude.

    Sketch conventions: 1 SVG user unit = 1 mm (``width``/``height`` in mm with a
    ``viewBox`` in the same numbers). The viewBox's bottom-left corner becomes the
    origin and the sketch keeps the orientation it is drawn in (SVG y is flipped on
    import). Every shape is imported as a filled area: strokes and colors are
    ignored, and separate shapes are unioned. Holes are sub-paths of the same
    ``<path>`` with ``fill-rule="evenodd"``.

    A sketch normally lives next to the module that uses it:
    ``load_sketch(Path(__file__).with_name("vslot_2020.svg"))``. ``fn`` sets the
    facet count of curves (default: the importer's own, about 28 per circle).
    """
    path = Path(path).resolve()  # the importer needs an absolute path
    if not path.is_file():
        raise FileNotFoundError(f"Sketch not found: {path}")
    return osimport(str(path)) if fn is None else osimport(str(path), fn=fn)


def teardrop(d: float) -> Solid:
    """2D horizontal-hole profile printable without support.

    A circle with a 45° point toward +Y, in the XY plane. Rotate it into place.
    """
    return circle(d=d, fn=FN_HOLE) | square([d / 2, d / 2]).rotate([0, 0, 45])


def teardrop_x(d: float, length: float) -> Solid:
    """Teardrop hole along the X axis (point up, +Z), centered on the origin."""
    return linear_extrude(teardrop(d), height=length, center=True).rotate([90, 0, 90])


def teardrop_y(d: float, length: float) -> Solid:
    """Teardrop hole along the Y axis (point up, +Z), centered on the origin."""
    return linear_extrude(teardrop(d), height=length, center=True).rotate([90, 0, 0])
