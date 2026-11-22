"""Solving the load cases of a part on one mesh: scaling proportional cases, in parallel."""

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from cadder.part import MaterialPart
from cadder.types import Vec3

from plotzker.fem import applied
from plotzker.fem.ccx import DEFAULT_SOLVER, Results, SolverMaterial, run_ccx, write_input
from plotzker.fem.mesh import Mesh

#: Cores CalculiX may use in total (the performance cores of a laptop).
MAX_THREADS = 8

Forces = dict[int, Vec3]


@dataclass
class Solved:
    """Results of every load case on one mesh."""

    mesh: Mesh
    results: dict[str, Results]
    forces: dict[str, Forces]
    body_load: dict[str, bool]
    solves: int  #: how many CalculiX runs it took (proportional cases are scaled, not run)


def proportional(base: Forces, other: Forces, tol: float = 1e-6) -> float | None:
    """The factor ``k`` with ``other = k * base`` for every nodal force, or ``None``."""
    if base.keys() != other.keys() or not base:
        return None
    node = max(base, key=lambda n: sum(c * c for c in base[n]))
    axis = max(range(3), key=lambda i: abs(base[node][i]))
    k = other[node][axis] / base[node][axis]
    scale = max(abs(c) for f in base.values() for c in f) * max(abs(k), 1.0)
    for n, f in base.items():
        if any(abs(other[n][i] - k * f[i]) > tol * scale for i in range(3)):
            return None
    return k


def solve_cases(
    part: MaterialPart,
    mesh: Mesh,
    material: SolverMaterial,
    work: Path,
    tag: str,
    log: Callable[[str], None],
    solver: str = DEFAULT_SOLVER,
) -> Solved:
    """Solve every load case of ``part`` on ``mesh``."""
    assert part.fem is not None
    supports = applied.support_nodes(mesh, part.fem.supports)
    forces: dict[str, Forces] = {}
    body: dict[str, bool] = {}
    accelerations: dict[str, Vec3 | None] = {}
    for case in part.fem.load_cases:
        f, acceleration = applied.case_loads(mesh, case)
        forces[case.name], accelerations[case.name] = f, acceleration
        body[case.name] = acceleration is not None

    base_of: dict[str, tuple[str, float]] = {}
    bases: list[str] = []
    for case in part.fem.load_cases:
        for earlier in bases:
            k = (
                None
                if accelerations[case.name] or accelerations[earlier]
                else proportional(forces[earlier], forces[case.name])
            )
            if k is not None:
                base_of[case.name] = (earlier, k)
                break
        else:
            bases.append(case.name)

    threads = max(1, min(MAX_THREADS, os.cpu_count() or 1) // len(bases))

    def run(name: str) -> Results:
        inp = work / f"{tag}_{name}.inp"
        write_input(
            inp,
            mesh,
            material,
            part.axis,
            supports,
            forces[name],
            accelerations[name],
            solver,
        )
        log(f"    solving {name} on {len(mesh.tets)} tets ({threads} threads)")
        return run_ccx(inp, threads)

    with ThreadPoolExecutor(max_workers=len(bases)) as pool:
        solved = dict(zip(bases, pool.map(run, bases), strict=True))
    results = {}
    for case in part.fem.load_cases:
        if case.name in solved:
            results[case.name] = solved[case.name]
        else:
            base, k = base_of[case.name]
            log(f"    {case.name}: {k:g} × {base} (linear, not solved again)")
            results[case.name] = solved[base].scaled(k)
    return Solved(mesh, results, forces, body, len(bases))
