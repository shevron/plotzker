"""CalculiX: write the input deck for one load case, run it and read the .frd results."""

import math
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from cadder.fem.mesh import Mesh
from cadder.tools import find_tool
from cadder.types import Vec3

Tensor = tuple[float, float, float, float, float, float]  #: xx, yy, zz, xy, yz, zx

#: Seconds CalculiX may take for one load case.
CCX_TIMEOUT_S = 900
#: 1 g/cm³ in the solver's unit system (mm, N, MPa → tonne/mm³).
G_CM3_TO_T_MM3 = 1e-9


@dataclass(frozen=True)
class SolverMaterial:
    """Transversely isotropic material (MPa, g/cm³); material axis 3 is the build direction."""

    e_in_plane: float
    e_build: float
    nu_in_plane: float
    nu_build: float
    g_build: float
    density_g_cm3: float


@dataclass(frozen=True)
class Supports:
    """Nodes held in the directions marked in ``constrain``."""

    nodes: frozenset[int]
    constrain: tuple[bool, bool, bool]


@dataclass(frozen=True)
class Results:
    """Nodal results of one run."""

    displacement: dict[int, Vec3]
    stress: dict[int, Tensor]  #: global axes
    reaction: dict[int, Vec3]

    def scaled(self, k: float) -> Results:
        """The results of a load case ``k`` times as large (the analysis is linear)."""
        return Results(
            {n: (u[0] * k, u[1] * k, u[2] * k) for n, u in self.displacement.items()},
            {
                n: (s[0] * k, s[1] * k, s[2] * k, s[3] * k, s[4] * k, s[5] * k)
                for n, s in self.stress.items()
            },
            {n: (r[0] * k, r[1] * k, r[2] * k) for n, r in self.reaction.items()},
        )


def local_axes(build: Vec3) -> tuple[Vec3, Vec3, Vec3]:
    """Material axes: 1 and 2 span the layer plane, 3 is the build direction (right-handed)."""
    n = math.sqrt(sum(c * c for c in build))
    e3 = (build[0] / n, build[1] / n, build[2] / n)
    helper = (1.0, 0.0, 0.0) if abs(e3[0]) < 0.9 else (0.0, 1.0, 0.0)
    d = sum(h * c for h, c in zip(helper, e3, strict=True))
    e1 = (helper[0] - d * e3[0], helper[1] - d * e3[1], helper[2] - d * e3[2])
    m = math.sqrt(sum(c * c for c in e1))
    e1 = (e1[0] / m, e1[1] / m, e1[2] / m)
    e2 = (
        e3[1] * e1[2] - e3[2] * e1[1],
        e3[2] * e1[0] - e3[0] * e1[2],
        e3[0] * e1[1] - e3[1] * e1[0],
    )
    return e1, e2, e3


#: Solver passed to ``*STATIC`` (``""``: CalculiX's default, SPOOLES).
DEFAULT_SOLVER = ""


def write_input(
    path: Path,
    mesh: Mesh,
    material: SolverMaterial,
    build: Vec3,
    supports: Sequence[Supports],
    forces: Mapping[int, Vec3],
    acceleration: Vec3 | None = None,
    solver: str = DEFAULT_SOLVER,
) -> None:
    """Write a static analysis deck with the given supports, nodal forces and body acceleration."""
    e1, e2, _ = local_axes(build)
    m = material
    g_in_plane = m.e_in_plane / (2 * (1 + m.nu_in_plane))
    out = ["*NODE, NSET=ALL"]
    out += [f"{n},{p[0]:.6g},{p[1]:.6g},{p[2]:.6g}" for n, p in mesh.nodes.items()]
    out.append("*ELEMENT, TYPE=C3D10, ELSET=EALL")
    out += [f"{i + 1}," + ",".join(map(str, tet)) for i, tet in enumerate(mesh.tets)]
    out += [
        "*MATERIAL, NAME=MAT",
        "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
        f"{m.e_in_plane:g},{m.e_in_plane:g},{m.e_build:g},{m.nu_in_plane:g},{m.nu_build:g},"
        f"{m.nu_build:g},{g_in_plane:g},{m.g_build:g},",
        f"{m.g_build:g}",
        "*DENSITY",
        f"{m.density_g_cm3 * G_CM3_TO_T_MM3:g}",
        "*ORIENTATION, NAME=OR, SYSTEM=RECTANGULAR",
        ",".join(f"{c:.8g}" for c in (*e1, *e2)),
        "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT, ORIENTATION=OR",
    ]
    for index, support in enumerate(supports):
        out.append(f"*NSET, NSET=SUP{index}")
        out += [str(n) for n in sorted(support.nodes)]
    out += ["*STEP", f"*STATIC, SOLVER={solver}" if solver else "*STATIC", "*BOUNDARY"]
    for index, support in enumerate(supports):
        for dof, fixed in enumerate(support.constrain, start=1):
            if fixed:
                out.append(f"SUP{index},{dof},{dof}")
    if forces:
        out.append("*CLOAD")
        for node, f in forces.items():
            out += [f"{node},{d},{c:.8g}" for d, c in enumerate(f, start=1) if c]
    if acceleration is not None and any(acceleration):
        a = math.sqrt(sum(c * c for c in acceleration))
        direction = ",".join(f"{-c / a:.8g}" for c in acceleration)
        out += ["*DLOAD", f"EALL,GRAV,{a:.8g},{direction}"]
    out += ["*NODE FILE", "U,RF", "*EL FILE", "S", "*END STEP"]
    path.write_text("\n".join(out) + "\n")


def run_ccx(inp: Path, threads: int = 1) -> Results:
    """Run CalculiX on ``inp`` with ``threads`` threads and read ``<name>.frd``."""
    try:
        result = subprocess.run(
            [str(find_tool("ccx")), inp.stem],
            cwd=inp.parent,
            capture_output=True,
            text=True,
            timeout=CCX_TIMEOUT_S,
            env=_thread_env(threads),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"CalculiX timed out on {inp.name}") from exc
    frd = inp.with_suffix(".frd")
    if result.returncode != 0 or not frd.is_file():
        text = result.stdout + result.stderr
        errors = [ln.strip() for ln in text.splitlines() if "ERROR" in ln or "nonpositive" in ln]
        raise RuntimeError(f"CalculiX failed on {inp.name}: {'; '.join(errors[:3]) or text[-300:]}")
    return read_frd(frd)


def _thread_env(threads: int) -> dict[str, str]:
    """Environment that makes CalculiX use ``threads`` threads."""
    n = str(max(1, threads))
    return {
        **os.environ,
        "OMP_NUM_THREADS": n,
        "CCX_NPROC_STIFFNESS": n,
        "CCX_NPROC_EQUATION_SOLVER": n,
        "CCX_NPROC_RESULTS": n,
    }


def read_frd(path: Path) -> Results:
    """Parse displacements (DISP), stresses (STRESS) and reactions (FORC) from a .frd file."""
    blocks: dict[str, dict[int, tuple[float, ...]]] = {}
    current: dict[int, tuple[float, ...]] | None = None
    for line in path.read_text().split("\n"):
        if line.startswith(" -4"):
            current = blocks.setdefault(line.split()[1], {})
        elif line.startswith(" -3") or line.startswith("    3"):
            current = None
        elif line.startswith(" -1") and current is not None:
            node = int(line[3:13])
            values = line[13:].rstrip()
            current[node] = tuple(
                float(values[i : i + 12])
                for i in range(0, len(values), 12)
                if values[i : i + 12].strip()
            )
    disp = {n: (v[0], v[1], v[2]) for n, v in blocks.get("DISP", {}).items()}
    stress = {n: (v[0], v[1], v[2], v[3], v[4], v[5]) for n, v in blocks.get("STRESS", {}).items()}
    reaction = {n: (v[0], v[1], v[2]) for n, v in blocks.get("FORC", {}).items()}
    if not disp or not stress:
        raise RuntimeError(f"{path.name}: no displacement or stress results")
    return Results(disp, stress, reaction)
