"""Handles: named 4×4 frames attached to solids, which follow them through transforms.

A part that hardware or other parts attach to exposes named handles (:func:`set_handles`);
assemblies place things with ``solid.align(handle)`` instead of repeating the part's
coordinates.
"""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pythonscad import multmatrix

from cadder.types import Matrix

if TYPE_CHECKING:
    from pythonscad import Solid


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


def frame_handle(origin: Sequence[float], u: Sequence[float], v: Sequence[float], w: Sequence[float]) -> Matrix:
    """A handle from an origin and three axis vectors (the columns of its rotation). Unlike
    :func:`handle` the axes may be left-handed: a mirrored, chiral part keeps its own frame."""
    return [[u[i], v[i], w[i], origin[i]] for i in range(3)] + [[0, 0, 0, 1]]


def frame_axes(mat: Matrix) -> tuple[list[float], list[float], list[float], list[float]]:
    """Origin and axes ``(origin, u, v, w)`` of a handle (the inverse of :func:`frame_handle`)."""
    return (
        [mat[i][3] for i in range(3)],
        [mat[i][0] for i in range(3)],
        [mat[i][1] for i in range(3)],
        [mat[i][2] for i in range(3)],
    )


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


def place_in_frame(
    solid: Solid,
    origin: Sequence[float],
    u: Sequence[float],
    v: Sequence[float],
    w: Sequence[float],
) -> Solid:
    """``solid`` (modeled in its own frame) with its axes along ``u``, ``v``, ``w``."""
    return multmatrix(solid, frame_handle(origin, u, v, w))
