"""Turning a part's loads and supports into nodal forces and constrained node sets."""

import math
from collections.abc import Sequence

from plotter_cad.fem.ccx import Supports
from plotter_cad.fem.mesh import Cover, Mesh, TriFace, cover_region, covered_nodes, covered_weights
from plotter_cad.part import Acceleration, Force, Load, LoadCase, Moment, Support
from plotter_cad.regions import Region
from plotter_cad.types import Vec3


class SpecError(ValueError):
    """The part's FEM spec doesn't fit its mesh (a region selects nothing, ...)."""


def _cover(mesh: Mesh, region: Region, what: str) -> list[Cover]:
    """The faces and sample points a region covers; an empty cover is a spec error."""
    covers = cover_region(mesh, region)
    if not covers:
        raise SpecError(f"{what}: the region selects no faces of the mesh")
    return covers


def force_on_region(
    mesh: Mesh, region: Region, vector: Vec3, what: str, bearing: bool = False
) -> dict[int, Vec3]:
    """A total force spread over the covered area (consistent nodal forces)."""
    face_weight = None
    if bearing:
        length = math.sqrt(sum(c * c for c in vector))
        unit = (vector[0] / length, vector[1] / length, vector[2] / length)

        def face_weight(face: TriFace) -> float:
            """Cosine of the angle between the force and the direction into the surface."""
            return max(0.0, -sum(face.normal[i] * unit[i] for i in range(3)))

    weights = covered_weights(_cover(mesh, region, what), face_weight)
    total = sum(weights.values())
    if total <= 0:
        raise SpecError(f"{what}: no covered face takes the load")
    return {
        n: (vector[0] * w / total, vector[1] * w / total, vector[2] * w / total)
        for n, w in weights.items()
    }


def moment_on_region(mesh: Mesh, region: Region, vector: Vec3, what: str) -> dict[int, Vec3]:
    """A pure couple as forces proportional to the lever arm about the region's centroid."""
    weights = covered_weights(_cover(mesh, region, what))
    total = sum(weights.values())
    centroid = [sum(mesh.nodes[n][i] * w for n, w in weights.items()) / total for i in range(3)]
    mag = math.sqrt(sum(c * c for c in vector))
    axis = tuple(c / mag for c in vector)
    arms = {n: [mesh.nodes[n][i] - centroid[i] for i in range(3)] for n in weights}
    inertia = 0.0
    for n, rho in arms.items():
        along = sum(rho[i] * axis[i] for i in range(3))
        inertia += weights[n] * (sum(c * c for c in rho) - along * along)
    if inertia <= 0:
        raise SpecError(f"{what}: the region is too small to carry a couple")
    forces: dict[int, Vec3] = {}
    for n, rho in arms.items():
        cx = vector[1] * rho[2] - vector[2] * rho[1]
        cy = vector[2] * rho[0] - vector[0] * rho[2]
        cz = vector[0] * rho[1] - vector[1] * rho[0]
        s = weights[n] / inertia
        forces[n] = (cx * s, cy * s, cz * s)
    return forces


def case_loads(mesh: Mesh, case: LoadCase) -> tuple[dict[int, Vec3], Vec3 | None]:
    """Nodal forces and the body acceleration (if any) of a load case."""
    forces: dict[int, Vec3] = {}
    acceleration: Vec3 | None = None
    for index, load in enumerate(case.loads):
        what = f"load case {case.name}, load {index + 1}"
        part = _one_load(mesh, load, what)
        if isinstance(part, tuple):
            acceleration = part
            continue
        for n, f in part.items():
            old = forces.get(n, (0.0, 0.0, 0.0))
            forces[n] = (old[0] + f[0], old[1] + f[1], old[2] + f[2])
    return forces, acceleration


def _one_load(mesh: Mesh, load: Load, what: str) -> dict[int, Vec3] | Vec3:
    """Nodal forces of one load, or the acceleration vector for a body load."""
    if isinstance(load, Force):
        return force_on_region(mesh, load.region, load.vector, what, load.bearing)
    if isinstance(load, Moment):
        return moment_on_region(mesh, load.region, load.vector, what)
    assert isinstance(load, Acceleration)
    return load.vector


def support_nodes(mesh: Mesh, supports: Sequence[Support]) -> list[Supports]:
    """The constrained node sets of a part's supports."""
    return [
        Supports(frozenset(covered_nodes(_cover(mesh, s.region, f"support {s.name}"))), s.constrain)
        for s in supports
    ]


def net_force(forces: dict[int, Vec3], supports: Sequence[Supports] = ()) -> Vec3:
    """Sum of the nodal forces on free directions (supports carry the rest directly)."""
    fixed: dict[int, list[bool]] = {}
    for support in supports:
        for n in support.nodes:
            old = fixed.setdefault(n, [False, False, False])
            fixed[n] = [old[i] or support.constrain[i] for i in range(3)]
    total = [0.0, 0.0, 0.0]
    for n, f in forces.items():
        mask = fixed.get(n, [False, False, False])
        for i in range(3):
            if not mask[i]:
                total[i] += f[i]
    return (total[0], total[1], total[2])
