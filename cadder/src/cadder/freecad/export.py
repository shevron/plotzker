"""Export a :class:`~cadder.freecad.model.FreeCadAssembly`: STLs and a manifest for the builder.

Writes ``<out>/<name>/stl/*.stl`` and ``<out>/<name>/manifest.json``. Components that are the
same shape in another place or orientation (wheels, motors, shaft supports...) share one STL:
each component's entry gets the placement (a ``rotation`` matrix about the bounding-box
``center``) that takes the shared mesh to its place. Only proper rotations that map the axes
onto themselves are tried (mirror images are different shapes).

The manifest (``version`` 1)::

    {"version", "name", "label", "description", "output": "<out>/<name>.FCStd",
     "components": [{"name", "body", "color", "transparency", "stl", "center", "rotation"}],
     "bodies": [{"name", "root", "grounded"}],
     "joints": [{"kind", "a", "b", "origin", "direction", "label", "limits"}],
     "metadata": {...}}
"""

import itertools
import json
import re
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import asdict
from functools import reduce
from pathlib import Path
from typing import Any

from cadder.freecad.model import Component, FreeCadAssembly

Rotation = tuple[tuple[int, ...], ...]

MANIFEST_VERSION = 1


def _rotations() -> list[Rotation]:
    """The 24 proper rotations that map the axes onto themselves (as integer matrices)."""
    found = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            rows = tuple(tuple(signs[r] if perm[r] == c else 0 for c in range(3)) for r in range(3))
            det = (
                rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
                - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
                + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
            )
            if det == 1:
                found.append(rows)
    return found


_ROTATIONS = _rotations()
_IDENTITY = _ROTATIONS[[r == ((1, 0, 0), (0, 1, 0), (0, 0, 1)) for r in _ROTATIONS].index(True)]
_TOL = 0.02  #: mm; two points closer than this are the same vertex


class _Shape:
    """Vertex cloud of an STL, centered on its bounding box."""

    def __init__(self, points: list[tuple[float, float, float]], facets: int) -> None:
        self.facets = facets
        low = [min(p[k] for p in points) for k in range(3)]
        high = [max(p[k] for p in points) for k in range(3)]
        self.center = tuple((a + b) / 2 for a, b in zip(low, high, strict=True))
        self.extents = tuple(round(b - a, 2) for a, b in zip(low, high, strict=True))
        self.points = [(p[0] - self.center[0], p[1] - self.center[1], p[2] - self.center[2]) for p in points]
        self.signature = (len(points), facets, tuple(sorted(self.extents)))

    @classmethod
    def read(cls, path: Path) -> _Shape:
        """Parse an ASCII STL."""
        vertices = [
            tuple(float(v) for v in line.split()[1:4])
            for line in path.read_text().splitlines()
            if line.lstrip().startswith("vertex")
        ]
        unique = list({(round(x, 3), round(y, 3), round(z, 3)) for x, y, z in vertices})
        return cls(unique, len(vertices) // 3)

    def maps_to(self, other: _Shape, rotation: Rotation) -> bool:
        """Whether ``other`` is this shape, rotated about the centers, point for point."""
        cell = 4 * _TOL
        grid: dict[tuple[int, int, int], list[tuple[float, float, float]]] = {}
        for p in other.points:
            grid.setdefault((round(p[0] / cell), round(p[1] / cell), round(p[2] / cell)), []).append(p)
        for x, y, z in self.points:
            q = tuple(r[0] * x + r[1] * y + r[2] * z for r in rotation)
            key = (round(q[0] / cell), round(q[1] / cell), round(q[2] / cell))
            if not any(
                abs(c[0] - q[0]) < _TOL and abs(c[1] - q[1]) < _TOL and abs(c[2] - q[2]) < _TOL
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                for dz in (-1, 0, 1)
                for c in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ())
            ):
                return False
        return True


def _congruent_groups(shapes: dict[str, _Shape]) -> list[list[tuple[str, Rotation]]]:
    """Group components that are the same shape (rotation + translation, no mirroring).

    Each group is ``[(name, rotation)]`` with the first member as the master (identity)."""
    groups: list[list[tuple[str, Rotation]]] = []
    for name, shape in shapes.items():
        for group in groups:
            master = shapes[group[0][0]]
            if master.signature != shape.signature:
                continue
            rotation = next((r for r in _ROTATIONS if master.maps_to(shape, r)), None)
            if rotation is not None:
                group.append((name, rotation))
                break
        else:
            groups.append([(name, _IDENTITY)])
    return groups


def shared_name(first: Component, size: int) -> str:
    """STL name for a group of ``size`` congruent components whose first one is ``first``: its
    ``shape``, or its name without a side / position / number suffix."""
    if size == 1:
        return first.name
    if first.shape:
        return first.shape
    return re.sub(r"(_[LR])?(_(top|bottom))?(_?\d+)?$", "", first.name)


def export_assembly(assembly: FreeCadAssembly, out_dir: Path, log: Callable[[str], None] = print) -> Path:
    """Write the assembly's STLs and manifest into ``out_dir/<name>/``; returns the manifest."""
    from pythonscad import export

    components = list(assembly.components())
    joints = list(assembly.joints())
    assembly.check(components, joints)
    folder = out_dir / assembly.name
    stl_dir = folder / "stl"
    stl_dir.mkdir(parents=True, exist_ok=True)
    for old in stl_dir.glob("*.stl"):
        old.unlink()
    by_name = {c.name: c for c in components}
    entries: dict[str, dict[str, Any]] = {
        c.name: {
            "name": c.name,
            "body": c.body,
            "color": list(c.color),
            "transparency": c.transparency,
        }
        for c in components
    }
    with tempfile.TemporaryDirectory() as tmp:
        shapes = {}
        for c in components:
            solid = c.solid
            if isinstance(solid, Sequence):
                solid = reduce(lambda a, b: a | b, solid)
            path = Path(tmp) / f"{c.name}.stl"
            export(solid, str(path))
            shapes[c.name] = _Shape.read(path)
        for members in _congruent_groups(shapes):
            master = members[0][0]
            stl_name = shared_name(by_name[master], len(members))
            text = (Path(tmp) / f"{master}.stl").read_text()
            (stl_dir / f"{stl_name}.stl").write_text(text)
            for name, rotation in members:
                entries[name]["stl"] = stl_name
                entries[name]["center"] = list(shapes[name].center)
                entries[name]["rotation"] = [v for row in rotation for v in row]
            shared = f" (x{len(members)}: {', '.join(n for n, _ in members)})"
            log(f"wrote {stl_name}.stl" + (shared if len(members) > 1 else ""))
    manifest = {
        "version": MANIFEST_VERSION,
        "name": assembly.name,
        "label": assembly.label,
        "description": assembly.description,
        "output": str(out_dir / f"{assembly.name}.FCStd"),
        "components": [entries[c.name] for c in components],
        "bodies": [asdict(b) for b in assembly.bodies],
        "joints": [asdict(j) for j in joints],
        "metadata": dict(assembly.metadata()),
    }
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest, indent=1) + "\n")
    log(f"wrote {path}")
    return path


def build_assembly(manifest: Path, log: Callable[[str], None] = print) -> Path:
    """Build the ``.FCStd`` from a manifest with FreeCAD's command-line binary; returns it."""
    import os
    import subprocess

    from cadder.tools import find_tool

    freecadcmd = find_tool("freecadcmd")
    builder = Path(__file__).with_name("build.py")
    env = {**os.environ, "CADDER_FREECAD_MANIFEST": str(manifest.resolve())}
    result = subprocess.run([str(freecadcmd), str(builder)], capture_output=True, text=True, env=env, check=False)
    output = Path(json.loads(manifest.read_text())["output"])
    summary = [ln for ln in result.stdout.splitlines() if ln.startswith(("solve()", "wrote"))]
    if result.returncode != 0 or not any(ln.startswith("wrote") for ln in summary):
        raise RuntimeError(
            f"FreeCAD build of {manifest.parent.name} failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    for line in summary:
        log(line)
    return output
