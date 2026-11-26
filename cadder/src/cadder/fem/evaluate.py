"""Judging results: failure index of printed material, displacement limits and verdicts."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from cadder.fem.ccx import Tensor, local_axes
from cadder.fem.mesh import Mesh
from cadder.types import Vec3

#: Share of a limit used at which a passing result is still called marginal.
MARGINAL_FROM = 0.85


class Status(StrEnum):
    """Outcome of one criterion or of a whole check, worst last."""

    PASS = "PASS"
    MARGINAL = "MARGINAL"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


def status_for(utilization: float) -> Status:
    """PASS up to :data:`MARGINAL_FROM` of the limit, MARGINAL up to the limit, FAIL beyond."""
    if utilization > 1:
        return Status.FAIL
    return Status.MARGINAL if utilization > MARGINAL_FROM else Status.PASS


def worst(statuses: Sequence[Status]) -> Status:
    """The most serious status (INCONCLUSIVE, then FAIL, MARGINAL, PASS)."""
    order = [Status.PASS, Status.MARGINAL, Status.FAIL, Status.INCONCLUSIVE]
    return max(statuses, key=order.index, default=Status.PASS)


@dataclass(frozen=True)
class Strengths:
    """Allowable stresses (MPa) of the real part, before the safety factor."""

    in_plane: float
    build: float  #: across the layers
    shear_build: float  #: shear between layers (ASSUMED equal to ``build``)


def to_local(stress: Tensor, build: Vec3) -> list[list[float]]:
    """The stress tensor in material axes (1, 2 in the layer plane, 3 along the build)."""
    axes = local_axes(build)
    sxx, syy, szz, sxy, syz, szx = stress
    matrix = [[sxx, sxy, szx], [sxy, syy, syz], [szx, syz, szz]]
    return [
        [sum(axes[i][a] * matrix[a][b] * axes[j][b] for a in range(3) for b in range(3)) for j in range(3)]
        for i in range(3)
    ]


def failure_index(stress: Tensor, build: Vec3, allow: Strengths) -> tuple[float, str]:
    """Failure index (1 = at the allowable) and the mode that governs it.

    Modes: ``in-plane`` (largest in-plane principal stress, tension or compression, over the
    in-plane strength) and ``interlayer`` (tension across the layers and shear between them,
    combined quadratically).
    """
    local_stress = to_local(stress, build)
    mean = (local_stress[0][0] + local_stress[1][1]) / 2
    radius = math.hypot((local_stress[0][0] - local_stress[1][1]) / 2, local_stress[0][1])
    in_plane = (abs(mean) + radius) / allow.in_plane
    tension = max(local_stress[2][2], 0.0) / allow.build
    shear = math.hypot(local_stress[0][2], local_stress[1][2]) / allow.shear_build
    interlayer = math.hypot(tension, shear)
    return (in_plane, "in-plane") if in_plane >= interlayer else (interlayer, "interlayer")


def stress_components(stress: Tensor, build: Vec3) -> tuple[float, float, float]:
    """In-plane principal stress of largest magnitude, stress across the layers (signed) and
    shear between the layers, all in MPa."""
    local_stress = to_local(stress, build)
    mean = (local_stress[0][0] + local_stress[1][1]) / 2
    radius = math.hypot((local_stress[0][0] - local_stress[1][1]) / 2, local_stress[0][1])
    principal = mean + radius if abs(mean + radius) >= abs(mean - radius) else mean - radius
    return principal, local_stress[2][2], math.hypot(local_stress[0][2], local_stress[1][2])


@dataclass(frozen=True)
class StressResult:
    """Peak failure index of a load case, with and without the singular spots."""

    peak: float  #: over all nodes
    peak_node: int
    peak_mode: str
    robust: float  #: excluding nodes near the edges of loaded and supported patches
    robust_node: int
    robust_mode: str


def stress_result(
    mesh: Mesh,
    stresses: dict[int, Tensor],
    build: Vec3,
    allow: Strengths,
    excluded: set[int],
) -> StressResult:
    """Failure index over all nodes, and over the nodes away from loads and supports."""
    peak = (-1.0, 0, "")
    robust = (-1.0, 0, "")
    for node, tensor in stresses.items():
        index_value, mode = failure_index(tensor, build, allow)
        if index_value > peak[0]:
            peak = (index_value, node, mode)
        if node not in excluded and index_value > robust[0]:
            robust = (index_value, node, mode)
    if robust[1] == 0:
        robust = peak
    return StressResult(peak[0], peak[1], peak[2], robust[0], robust[1], robust[2])


def near_nodes(mesh: Mesh, seeds: set[int], radius: float) -> set[int]:
    """Nodes within ``radius`` of any seed node (spatial hash, so it stays fast)."""
    cell = max(radius, 1e-6)
    grid: dict[tuple[int, int, int], list[Vec3]] = {}
    for node in seeds:
        position = mesh.nodes[node]
        grid.setdefault((int(position[0] // cell), int(position[1] // cell), int(position[2] // cell)), []).append(
            position
        )
    found: set[int] = set()
    for node, position in mesh.nodes.items():
        cx, cy, cz = int(position[0] // cell), int(position[1] // cell), int(position[2] // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other in grid.get((cx + dx, cy + dy, cz + dz), ()):
                        if (position[0] - other[0]) ** 2 + (position[1] - other[1]) ** 2 + (
                            position[2] - other[2]
                        ) ** 2 <= radius**2:
                            found.add(node)
    return found


def displacement_value(
    displacement: dict[int, Vec3], nodes: Sequence[int], direction: Vec3 | None
) -> tuple[float, int]:
    """Largest displacement (magnitude, or absolute component along ``direction``) and its node."""
    unit = None
    if direction is not None:
        length = math.sqrt(sum(c * c for c in direction))
        unit = tuple(c / length for c in direction)
    best = (-1.0, nodes[0])
    for n in nodes:
        moved = displacement[n]
        value = (
            math.sqrt(sum(c * c for c in moved)) if unit is None else abs(sum(moved[i] * unit[i] for i in range(3)))
        )
        if value > best[0]:
            best = (value, n)
    return best
