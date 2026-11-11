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


#: A handle: a 4×4 transformation matrix marking a position and orientation on a part.
Matrix = list[list[float]]


def handle(position: Sequence[float], rotation: Sequence[float] = (0, 0, 0)) -> Matrix:
    """A handle at ``position`` turned by ``rotation`` (degrees about x, y, z, as ``rotate``).

    ``part.align(handle)`` puts a part modeled at the origin where
    ``part.rotate(rotation).translate(position)`` would.
    """
    ax, ay, az = (math.radians(a) for a in rotation)
    cx, cy, cz = math.cos(ax), math.cos(ay), math.cos(az)
    sx, sy, sz = math.sin(ax), math.sin(ay), math.sin(az)
    return [  # Rz · Ry · Rx, then the translation
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx, position[0]],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx, position[1]],
        [-sy, cy * sx, cy * cx, position[2]],
        [0, 0, 0, 1],
    ]


def shift_handle(mat: Matrix, offset: Sequence[float]) -> Matrix:
    """``mat`` moved by ``offset`` in the frame it is expressed in (not along its own axes)."""
    moved = [row[:] for row in mat]
    for i in range(3):
        moved[i][3] += offset[i]
    return moved


def set_handles(solid: Solid, **handles: Matrix | list[Matrix]) -> Solid:
    """Attach named handles to ``solid``; they follow it through transforms, mirroring and
    boolean operations (but not ``fillet``).

    A list becomes the numbered handles ``name_0``, ``name_1``... (PythonSCAD only
    transforms attributes that are matrices, not lists of them); read it with
    :func:`get_handles`.
    """
    for name, value in handles.items():
        if isinstance(value[0][0], list):
            for i, mat in enumerate(value):
                setattr(solid, f"{name}_{i}", mat)
        else:
            setattr(solid, name, value)
    return solid


def get_handle(solid: Solid, name: str) -> Matrix:
    """The handle ``name`` of ``solid``; a missing name raises ``AttributeError``."""
    value: Matrix = getattr(solid, name)
    return value


def get_handles(solid: Solid, name: str) -> list[Matrix]:
    """The numbered handles ``name_0``, ``name_1``... set from a list, in order."""
    found: list[Matrix] = []
    while hasattr(solid, f"{name}_{len(found)}"):
        found.append(get_handle(solid, f"{name}_{len(found)}"))
    if not found:
        raise AttributeError(f"{name}_0")
    return found


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
