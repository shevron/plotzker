"""Pictures of a FEM result: export the fields, then render them with VTK (FreeCAD's Python)."""

import json
import subprocess
from pathlib import Path

from plotzker.fem.ccx import Tensor
from plotzker.fem.evaluate import Strengths, failure_index
from plotzker.fem.mesh import Mesh
from plotzker.fem.tools import find_tool
from plotzker.types import Vec3

RENDER_SCRIPT = Path(__file__).with_name("viz_render.py")
#: Seconds the renderer may take for one load case.
RENDER_TIMEOUT_S = 300


def node_utilization(
    stresses: dict[int, Tensor], build: Vec3, allow: Strengths, safety_factor: float
) -> dict[int, float]:
    """Failure index × safety factor at every node (1.0 = at the allowable)."""
    return {n: failure_index(s, build, allow)[0] * safety_factor for n, s in stresses.items()}


def _outward_triangles(mesh: Mesh, index: dict[int, int]) -> list[list[int]]:
    """Boundary triangles (corner indices) wound counter-clockwise seen from outside."""
    tris = []
    for face in mesh.faces:
        a, b, c = face.nodes[:3]
        p, q, r = (mesh.nodes[n] for n in (a, b, c))
        ux, uy, uz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
        vx, vy, vz = r[0] - p[0], r[1] - p[1], r[2] - p[2]
        cross = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        flip = sum(cross[i] * face.normal[i] for i in range(3)) < 0
        tris.append([index[a], index[c], index[b]] if flip else [index[a], index[b], index[c]])
    return tris


def write_case_data(
    path: Path,
    *,
    part: str,
    case: str,
    mesh: Mesh,
    displacement: dict[int, Vec3],
    utilization: dict[int, float],
    hotspot: int,
    marks: list[tuple[int, str]],
    lines: list[str],
) -> None:
    """The fields of one load case for the renderer, as JSON (nodes referenced by index)."""
    ids = list(mesh.nodes)
    index = {n: i for i, n in enumerate(ids)}

    data = {
        "part": part,
        "case": case,
        "xyz": [mesh.nodes[n] for n in ids],
        "u": [displacement[n] for n in ids],
        "util": [utilization.get(n, 0.0) for n in ids],
        "tets": [[index[n] for n in tet] for tet in mesh.tets],
        "tris": _outward_triangles(mesh, index),
        "hotspot": index[hotspot],
        "marks": [[index[n], label] for n, label in marks],
        "lines": lines,
    }
    path.write_text(json.dumps(data, separators=(",", ":")))


def render(data_files: list[Path], out_dir: Path) -> list[Path]:
    """Render the pictures and ``.vtu`` of every data file; returns the files written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for data in data_files:
        result = subprocess.run(
            [str(find_tool("python")), str(RENDER_SCRIPT), str(data), str(out_dir)],
            capture_output=True,
            text=True,
            timeout=RENDER_TIMEOUT_S,
        )
        if result.returncode != 0:
            raise RuntimeError(f"rendering {data.name} failed: {result.stderr.strip()[-300:]}")
        written += [out_dir / name for name in result.stdout.split() if name]
    return written
