"""STL cleaning for the mesher: PythonSCAD leaves slivers that gmsh and CalculiX choke on."""

import re
from dataclasses import dataclass
from pathlib import Path

from plotter_cad.types import Vec3

#: Vertices closer than this (mm) are welded together.
WELD_TOL = 1e-3
#: Triangles with twice the area below this (mm²) are dropped.
MIN_DOUBLE_AREA = 1e-4

_VERTEX = re.compile(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)")


@dataclass(frozen=True)
class CleanStl:
    """A cleaned STL and what was done to it."""

    path: Path
    triangles: int
    dropped: int
    volume_mm3: float
    bbox: tuple[Vec3, Vec3]


def _cross(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    """Cross product of the edges ab and ac."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


def clean_stl(source: Path, dest: Path) -> CleanStl:
    """Weld vertices, drop degenerate and zero-area triangles, make the normals point outward."""
    text = source.read_text()
    raw = [(float(x), float(y), float(z)) for x, y, z in _VERTEX.findall(text)]
    welded: dict[tuple[int, int, int], Vec3] = {}

    def weld(p: Vec3) -> Vec3:
        key = (round(p[0] / WELD_TOL), round(p[1] / WELD_TOL), round(p[2] / WELD_TOL))
        return welded.setdefault(key, (key[0] * WELD_TOL, key[1] * WELD_TOL, key[2] * WELD_TOL))

    triangles: list[tuple[Vec3, Vec3, Vec3]] = []
    dropped = 0
    for i in range(0, len(raw) - 2, 3):
        a, b, c = weld(raw[i]), weld(raw[i + 1]), weld(raw[i + 2])
        cx, cy, cz = _cross(a, b, c)
        if cx * cx + cy * cy + cz * cz < MIN_DOUBLE_AREA**2:
            dropped += 1
        else:
            triangles.append((a, b, c))
    volume = (
        sum(
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
            for a, b, c in triangles
        )
        / 6
    )
    if volume < 0:
        triangles = [(a, c, b) for a, b, c in triangles]
        volume = -volume
    lines = ["solid part"]
    for tri in triangles:
        lines.append("facet normal 0 0 0\nouter loop")
        lines += [f"vertex {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}" for p in tri]
        lines.append("endloop\nendfacet")
    lines.append("endsolid part")
    dest.write_text("\n".join(lines) + "\n")
    points = [p for tri in triangles for p in tri]
    bbox = (
        (min(p[0] for p in points), min(p[1] for p in points), min(p[2] for p in points)),
        (max(p[0] for p in points), max(p[1] for p in points), max(p[2] for p in points)),
    )
    return CleanStl(dest, len(triangles), dropped, volume, bbox)
