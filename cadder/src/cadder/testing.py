"""Measurements on PythonSCAD solids, for a project's tests.

Everything works on the solid's mesh, so no STL export is needed.
"""

import itertools
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pythonscad import Solid

Box = tuple[list[float], list[float]]

#: How far apart two faces may be and still count as touching (mm).
TOUCH = 0.05


def flatten(items: object) -> Iterator[Solid]:
    """The solids of an assembly: assemblies return (possibly nested) lists."""
    if isinstance(items, (list, tuple)):
        for item in items:
            yield from flatten(item)
    else:
        yield items  # type: ignore[misc]


def volume(solid: Solid) -> float:
    """Enclosed volume of a 3D solid (mm³)."""
    points, faces = solid.mesh()
    total = 0.0
    for face in faces:
        ax, ay, az = points[face[0]]
        for i, j in itertools.pairwise(face[1:]):
            (bx, by, bz), (cx, cy, cz) = points[i], points[j]
            total += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return total / 6


def bounding_box(solid: Solid) -> Box:
    """``(lowest corner, highest corner)`` of a 3D solid."""
    points, _ = solid.mesh()
    return (
        [min(p[i] for p in points) for i in range(3)],
        [max(p[i] for p in points) for i in range(3)],
    )


def shell_count(solid: Solid) -> int:
    """Number of separate closed surfaces of a solid.

    1 for an ordinary one-piece part; more if it has loose pieces or enclosed voids.
    """
    points, faces = solid.mesh()
    parent = list(range(len(points)))

    def find(i: int) -> int:
        """Root of ``i``'s group, with path compression."""
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for face in faces:
        for vertex in face[1:]:
            parent[find(vertex)] = find(face[0])
    return len({find(vertex) for face in faces for vertex in face})


def touching(a: Solid, b: Solid, box_a: Box | None = None, box_b: Box | None = None) -> bool:
    """True if two solids overlap or have faces within :data:`TOUCH` of each other."""
    (a_lo, a_hi), (b_lo, b_hi) = box_a or bounding_box(a), box_b or bounding_box(b)
    if any(a_lo[i] > b_hi[i] + TOUCH or b_lo[i] > a_hi[i] + TOUCH for i in range(3)):
        return False
    nudges: list[list[float]] = [[0.0, 0.0, 0.0]] + [
        [sign * TOUCH if axis == i else 0.0 for i in range(3)] for axis in range(3) for sign in (1, -1)
    ]
    return any(volume(a & b.translate(nudge)) > 1e-6 for nudge in nudges)


def connected_groups(items: Iterable[object]) -> list[list[int]]:
    """Group the solids of an assembly that touch each other, directly or through others.

    Returns lists of item indices, largest group first. A fully connected assembly
    gives a single group; anything else floats in mid-air.
    """
    solids = list(flatten(items))
    boxes = [bounding_box(s) for s in solids]
    group = list(range(len(solids)))
    for i, j in itertools.combinations(range(len(solids)), 2):
        if group[i] != group[j] and touching(solids[i], solids[j], boxes[i], boxes[j]):
            group = [group[i] if label == group[j] else label for label in group]
    groups: dict[int, list[int]] = {}
    for index, label in enumerate(group):
        groups.setdefault(label, []).append(index)
    return sorted(groups.values(), key=len, reverse=True)
