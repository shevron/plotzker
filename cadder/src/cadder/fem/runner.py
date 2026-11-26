"""Run the FEM check of a part: mesh, solve every load case, judge, and write the results."""

import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from cadder.fem import applied
from cadder.fem.ccx import DEFAULT_SOLVER, Results, SolverMaterial
from cadder.fem.evaluate import (
    Status,
    Strengths,
    displacement_value,
    near_nodes,
    status_for,
    stress_components,
    stress_result,
    worst,
)
from cadder.fem.mesh import (
    STRATEGIES,
    Mesh,
    SizeField,
    cover_region,
    mesh_stl,
    nodes_in_region,
    patch_edge_nodes,
)
from cadder.fem.solve import Forces, Solved, solve_cases
from cadder.fem.stl import CleanStl, clean_stl
from cadder.fem.viz import node_utilization, render, write_case_data
from cadder.part import MaterialPart, part_to_dict
from cadder.regions import Region

#: Facet count for the part's STL: coarse holes keep the mesher fast.
FEM_FACETS = 20
#: How much finer the second mesh of the convergence check is.
REFINEMENT = 1.6
#: Allowed change of the external work (compliance) between the two meshes.
CONVERGENCE_TOL = 0.05
#: Allowed unbalance of reaction forces against the applied loads (share of the load).
EQUILIBRIUM_TOL = 0.01
#: Allowed difference between mesh and STL volume.
VOLUME_TOL = 0.02
#: Element size (mm) near loads and supports for small and large parts.
SMALL_PART_SIZE, LARGE_PART_SIZE, SMALL_PART_LIMIT = 2.0, 2.2, 80.0
#: Far elements are this many times the near size (at most MAX_FAR_SIZE mm).
GRADING, MAX_FAR_SIZE = 2.5, 6.0
#: A second, finer mesh is solved when a criterion's utilization is inside this band.
REFINE_BAND = (0.6, 1.6)


@dataclass
class Criterion:
    """One checked criterion of one load case."""

    name: str
    case: str
    value: float
    limit: float
    unit: str
    utilization: float
    status: Status
    detail: str = ""


@dataclass
class Check:
    """A sanity check of the analysis itself."""

    name: str
    ok: bool
    detail: str


@dataclass
class FemResult:
    """Everything one run produced."""

    part: str
    status: Status
    criteria: list[Criterion] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    assumed: list[str] = field(default_factory=list)
    mesh: dict[str, object] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    pictures: list[str] = field(default_factory=list)
    seconds: float = 0.0

    def to_dict(self) -> dict[str, object]:
        """JSON-ready form."""
        data = asdict(self)
        data["status"] = self.status.value
        for row in data["criteria"]:
            row["status"] = row["status"].value
        return data


def export_part_stl(part: MaterialPart, dest: Path, project: str) -> None:
    """Export the part in its analysis frame with coarse facets: a subprocess, because the facet
    count is read when the geometry modules are imported. ``project`` is the project's spec."""
    if not project:
        raise RuntimeError(f"STL export of {part.name}: no project spec to export it from")
    env = {**os.environ, "CADDER_FN": str(FEM_FACETS)}
    cmd = [sys.executable, "-m", "cadder", "--project", project, "part", part.name]
    result = subprocess.run(
        [*cmd, "--stl", str(dest)],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0 or not dest.is_file():
        raise RuntimeError(f"STL export of {part.name} failed: {result.stderr.strip()[-300:]}")


def _solver_material(part: MaterialPart) -> SolverMaterial:
    """The part's effective material in solver units."""
    eff = part.effective_properties()
    mat = part.material
    return SolverMaterial(
        eff["e_in_plane_mpa"],
        eff["e_build_mpa"],
        mat.nu_in_plane,
        mat.nu_build,
        eff["g_build_mpa"],
        mat.density_g_cm3,
    )


def _mesh_and_solve(
    part: MaterialPart,
    stl: Path,
    size_field: SizeField,
    work: Path,
    tag: str,
    options: RunOptions,
    log: Callable[[str], None],
) -> Solved:
    """Mesh and solve; if CalculiX fails on the mesh, mesh again with the next gmsh setting."""
    material = _solver_material(part)
    first = 0
    while first < len(STRATEGIES):
        mesh = mesh_stl(stl, size_field, work, tag, first)
        log(f"  {tag} mesh: {len(mesh.tets)} tets")
        try:
            return solve_cases(part, mesh, material, work, tag, log, options.solver)
        except RuntimeError as exc:
            if "CalculiX failed" not in str(exc) or mesh.strategy + 1 >= len(STRATEGIES):
                raise
            log(f"    CalculiX failed on the {tag} mesh ({str(exc)[:70]}); meshing again")
            first = mesh.strategy + 1
    raise RuntimeError(f"no usable {tag} mesh of {part.name}")


def _strengths(part: MaterialPart, sustained: bool) -> Strengths:
    """Allowable stresses for a load case (creep factor for sustained loads)."""
    eff = part.effective_properties()
    if sustained:
        return Strengths(
            eff["sustained_strength_in_plane_mpa"],
            eff["sustained_strength_build_mpa"],
            eff["sustained_strength_build_mpa"],
        )
    return Strengths(eff["strength_in_plane_mpa"], eff["strength_build_mpa"], eff["strength_build_mpa"])


def _named_regions(part: MaterialPart) -> list[tuple[str, Region]]:
    """Labeled regions of the part's supports and loads (where the mesh needs to be fine)."""
    assert part.fem is not None
    named = [(f"support {sup.name}", sup.region) for sup in part.fem.supports]
    for case in part.fem.load_cases:
        for index, load in enumerate(case.loads, start=1):
            region = getattr(load, "region", None)
            if region is not None:
                named.append((f"load {case.name} #{index}", region))
    return named


def _load_regions(part: MaterialPart) -> list[Region]:
    """Regions of the part's loads and supports."""
    return [region for _, region in _named_regions(part)]


def _patch_edges(part: MaterialPart, mesh: Mesh) -> dict[str, set[int]]:
    """Nodes on the outline of every loaded and supported patch, by label."""
    return {
        label: patch_edge_nodes([c.face for c in cover_region(mesh, region)]) for label, region in _named_regions(part)
    }


def _excluded_nodes(part: MaterialPart, mesh: Mesh) -> set[int]:
    """Nodes near the edges of loaded and supported patches, where stress peaks are artifacts."""
    edge: set[int] = set()
    for nodes in _patch_edges(part, mesh).values():
        edge |= nodes
    return near_nodes(mesh, edge, 1.5 * mesh.size)


def _nearest_patch(mesh: Mesh, node: int, edges: dict[str, set[int]]) -> tuple[str, float]:
    """The loaded or supported patch whose outline is closest to ``node``, and the distance."""
    target = mesh.nodes[node]
    best = ("none", math.inf)
    for label, nodes in edges.items():
        for other in nodes:
            position = mesh.nodes[other]
            distance = math.sqrt(
                (target[0] - position[0]) ** 2 + (target[1] - position[1]) ** 2 + (target[2] - position[2]) ** 2
            )
            if distance < best[1]:
                best = (label, distance)
    return best


def _external_work(forces: Forces, results: Results) -> float:
    """Work of the applied nodal forces on the computed displacements (twice the strain energy)."""
    return sum(sum(f[i] * results.displacement[n][i] for i in range(3)) for n, f in forces.items())


def _max_displacement(results: Results) -> float:
    """Largest displacement magnitude of a run."""
    return max(math.sqrt(sum(c * c for c in u)) for u in results.displacement.values())


@dataclass(frozen=True)
class RunOptions:
    """How a check is run."""

    size: float | None = None  #: element size near loads and supports (mm)
    refine: Literal["auto", "always", "never"] = "auto"
    graded: bool = True  #: coarse elements away from loads and supports
    solver: str = DEFAULT_SOLVER
    viz: bool = False  #: also write pictures and a .vtu per load case
    #: the project's spec (``"package.module:PROJECT"``): the part is exported in a subprocess
    project: str = ""


def _size_field(part: MaterialPart, extent: float, options: RunOptions) -> SizeField:
    """Element sizes: fine near the loads and supports, coarser elsewhere."""
    near = options.size or (SMALL_PART_SIZE if extent <= SMALL_PART_LIMIT else LARGE_PART_SIZE)
    if not options.graded:
        return SizeField(near, near)
    far = min(GRADING * near, MAX_FAR_SIZE)
    margin = 2 * near
    boxes = []
    for region in _load_regions(part):
        low, high = region.bounds()
        boxes.append(
            (
                (low[0] - margin, low[1] - margin, low[2] - margin),
                (high[0] + margin, high[1] + margin, high[2] + margin),
            )
        )
    return SizeField(near, far, tuple(boxes), transition=3 * near)


def _judge(part: MaterialPart, solved: Solved, reference: Solved | None) -> list[Criterion]:
    """Strength and displacement criteria of every load case on one mesh."""
    spec = part.fem
    assert spec is not None
    mesh = solved.mesh
    edges = _patch_edges(part, mesh)
    excluded = near_nodes(mesh, set().union(*edges.values()), 1.5 * mesh.size)
    excluded_ref = _excluded_nodes(part, reference.mesh) if reference else set()
    rows = []
    for case in spec.load_cases:
        safety_factor = case.safety_factor or spec.safety_factor
        run = solved.results[case.name]
        allow = _strengths(part, case.sustained)
        stresses = stress_result(mesh, run.stress, part.axis, allow, excluded)
        util = stresses.robust * safety_factor
        status = status_for(util)
        note = ""
        if stresses.peak * safety_factor > 1 and status is not Status.FAIL:
            status = worst([status, Status.MARGINAL])
            note = f"; raw peak {stresses.peak * safety_factor:.2f} exceeds the limit next to a load or support edge"
        if reference:
            ref = stress_result(
                reference.mesh,
                reference.results[case.name].stress,
                part.axis,
                allow,
                excluded_ref,
            )
            drift = (stresses.robust - ref.robust) / max(ref.robust, 1e-12)
            note += f"; peak stress changed {drift:+.0%} from the first mesh"
            if abs(drift) > 0.25:
                note += " (sharp-corner singularity likely: judge with care)"
        where = tuple(round(c, 1) for c in mesh.nodes[stresses.robust_node])
        principal, across, shear = stress_components(run.stress[stresses.robust_node], part.axis)
        patch, distance = _nearest_patch(mesh, stresses.robust_node, edges)
        rows.append(
            Criterion(
                f"strength/{case.name}",
                case.name,
                round(util, 3),
                1.0,
                "utilization (failure index × safety factor)",
                round(util, 3),
                status,
                f"{stresses.robust_mode} governs at {where}, failure index "
                f"{stresses.robust:.3f} × SF {safety_factor:g}; "
                f"there: in-plane principal {principal:.1f} MPa (allowable "
                f"{allow.in_plane:.1f}), across the layers {across:+.1f} MPa and interlayer "
                f"shear {shear:.1f} MPa (allowable {allow.build:.1f}); {distance:.1f} mm from "
                f"the edge of {patch}{note}",
            )
        )
        limits = spec.displacement_limits
        if not limits and spec.default_displacement_limit_mm is not None:
            value, node = displacement_value(run.displacement, list(mesh.nodes), None)
            rows.append(
                _displacement_row(
                    "default_displacement",
                    case.name,
                    value,
                    spec.default_displacement_limit_mm,
                    node,
                    mesh,
                )
            )
        for lim in limits:
            if lim.load_cases and case.name not in lim.load_cases:
                continue
            nodes = nodes_in_region(mesh, lim.region)
            if not nodes:
                raise applied.SpecError(f"limit {lim.name}: the region contains no mesh nodes")
            value, node = displacement_value(run.displacement, nodes, lim.direction)
            rows.append(_displacement_row(lim.name, case.name, value, lim.limit_mm, node, mesh))
    return rows


def _equilibrium(part: MaterialPart, solved: Solved) -> list[Check]:
    """Reactions must balance the loads on the free directions."""
    assert part.fem is not None
    supports = applied.support_nodes(solved.mesh, part.fem.supports)
    support_set = set().union(*(s.nodes for s in supports))
    checks = []
    for case in part.fem.load_cases:
        run, forces = solved.results[case.name], solved.forces[case.name]
        total = applied.net_force(forces, supports)
        reaction = [0.0, 0.0, 0.0]
        for n in support_set:
            support_reaction = run.reaction.get(n, (0.0, 0.0, 0.0))
            reaction = [reaction[i] + support_reaction[i] for i in range(3)]
        scale = sum(math.sqrt(sum(c * c for c in f)) for f in forces.values()) or 1.0
        unbalance = math.sqrt(sum((total[i] + reaction[i]) ** 2 for i in range(3))) / scale
        body = solved.body_load[case.name]
        checks.append(
            Check(
                f"equilibrium/{case.name}",
                body or unbalance <= EQUILIBRIUM_TOL,
                f"reactions {tuple(round(c, 3) for c in reaction)} vs applied "
                f"{tuple(round(c, 3) for c in total)}: unbalance {unbalance:.2%}"
                + (" (body load: not checked)" if body else ""),
            )
        )
    return checks


def _convergence(part: MaterialPart, first: Solved, second: Solved) -> list[Check]:
    """The compliance (external work) must agree between the two meshes."""
    assert part.fem is not None
    checks = []
    for case in part.fem.load_cases:
        a, b = first.results[case.name], second.results[case.name]
        max_a, max_b = _max_displacement(a), _max_displacement(b)
        work_a = _external_work(first.forces[case.name], a)
        work_b = _external_work(second.forces[case.name], b)
        if work_b > 0:
            change = abs(work_b - work_a) / work_b
            metric = f"external work {work_a:.4g} → {work_b:.4g} N·mm"
        else:
            change, metric = abs(max_b - max_a) / max(max_b, 1e-12), "largest displacement"
        checks.append(
            Check(
                f"convergence/{case.name}",
                change <= CONVERGENCE_TOL,
                f"{metric} ({change:.1%} change); largest displacement {max_a:.4f} → "
                f"{max_b:.4f} mm ({abs(max_b - max_a) / max(max_b, 1e-12):.1%})",
            )
        )
    return checks


def _pictures(
    part: MaterialPart,
    final: Solved,
    criteria: list[Criterion],
    work: Path,
    log: Callable[[str], None],
) -> list[str]:
    """Render pictures and a .vtu of every load case into ``work/viz``."""
    spec = part.fem
    assert spec is not None
    excluded = _excluded_nodes(part, final.mesh)
    data_files = []
    for case in spec.load_cases:
        allow = _strengths(part, case.sustained)
        safety_factor = case.safety_factor or spec.safety_factor
        run = final.results[case.name]
        util = node_utilization(run.stress, part.axis, allow, safety_factor)
        hotspot = stress_result(final.mesh, run.stress, part.axis, allow, excluded)
        rows = [c for c in criteria if c.case == case.name]
        lines = [f"{part.name} / {case.name}: {worst([c.status for c in rows]).value}"]
        lines += [
            f"{c.name}: {c.value:g} of {c.limit:g} {c.unit.split()[0]} ({c.utilization:.0%}) {c.status.value}"
            for c in rows
        ]
        path = work / f"viz_{case.name}.json"
        write_case_data(
            path,
            part=part.name,
            case=case.name,
            mesh=final.mesh,
            displacement=run.displacement,
            utilization=util,
            hotspot=hotspot.robust_node,
            marks=[],
            lines=lines,
        )
        data_files.append(path)
    log("  rendering pictures")
    try:
        written = render(data_files, work / "viz")
    finally:
        for path in data_files:
            path.unlink(missing_ok=True)
    return [f"viz/{f.name}" for f in written]


def _keep_only(work: Path, tag: str) -> None:
    """Keep the files of mesh ``tag`` under the fixed name ``final``; delete the others."""
    for path in list(work.glob("coarse*")) + list(work.glob("fine*")):
        if path.name.split(".")[0].split("_")[0] == tag:
            path.rename(path.with_name("final" + path.name[len(tag) :]))
        else:
            path.unlink()


def analyze(
    part: MaterialPart,
    out_dir: Path,
    options: RunOptions = RunOptions(),  # noqa: B008 - frozen, shared on purpose
    log: Callable[[str], None] = print,
    stl: Path | None = None,
) -> FemResult:
    """Check ``part`` against its FEM spec; files go to ``out_dir/<part name>/``.

    A first mesh is solved; a finer one only if a criterion is close enough to its limit for
    discretization error to matter (or if asked). ``stl`` supplies the geometry directly (tests);
    otherwise the part is exported.
    """
    spec = part.fem
    if spec is None:
        raise applied.SpecError(f"{part.name} has no FEM spec (fem_status: {part.fem_status})")
    started = time.time()
    work = out_dir / part.name
    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob("*"):
        if old.is_file():
            old.unlink()
    result = FemResult(part.name, Status.PASS)

    log(f"  exporting and cleaning the STL ({FEM_FACETS} facets per hole)")
    raw = stl or work / "part_raw.stl"
    if stl is None:
        export_part_stl(part, raw, options.project)
    clean: CleanStl = clean_stl(raw, work / "part.stl")
    extent = max(clean.bbox[1][i] - clean.bbox[0][i] for i in range(3))
    size_field = _size_field(part, extent, options)

    first = _mesh_and_solve(part, clean.path, size_field, work, "coarse", options, log)
    criteria = _judge(part, first, None)
    near_limit = any(REFINE_BAND[0] <= c.utilization <= REFINE_BAND[1] for c in criteria)
    refine = options.refine == "always" or (options.refine == "auto" and near_limit)
    final, tag = first, "coarse"
    if refine:
        log(f"  a criterion is within {REFINE_BAND} of its limit: refining the mesh")
        final = _mesh_and_solve(part, clean.path, size_field.scaled(1 / REFINEMENT), work, "fine", options, log)
        tag = "fine"
        criteria = _judge(part, final, first)
        result.checks += _convergence(part, first, final)
        result.notes.append(f"two meshes ({len(first.mesh.tets)} and {len(final.mesh.tets)} tets)")
    else:
        result.notes.append(
            f"single mesh ({len(first.mesh.tets)} tets): no criterion within {REFINE_BAND} of its "
            "limit, so refinement would not change a verdict"
        )
    result.criteria = criteria
    result.checks += _equilibrium(part, final)
    vol = final.mesh.volume()
    result.checks.append(
        Check(
            "volume",
            abs(vol - clean.volume_mm3) / clean.volume_mm3 <= VOLUME_TOL,
            f"mesh {vol:.0f} vs STL {clean.volume_mm3:.0f} mm³",
        )
    )
    result.mesh = {
        "element_size_mm": {"near": size_field.near, "far": size_field.far},
        "tets": len(final.mesh.tets),
        "solves": first.solves + (final.solves if refine else 0),
        "stl_triangles": clean.triangles,
        "stl_triangles_dropped": clean.dropped,
    }
    result.assumed = _assumed_inputs(part)
    result.notes.append(
        "Supports are fixed constraints (no contact), loads are spread over regions; "
        f"strength is judged away from the edges of loaded and supported patches "
        f"({1.5 * final.mesh.size:.1f} mm)"
    )
    result.status = (
        Status.INCONCLUSIVE if not all(c.ok for c in result.checks) else worst([c.status for c in result.criteria])
    )
    result.files = {
        "stl": "part.stl",
        "mesh": "final.msh",
        "inputs": "final_<case>.inp",
        "results": "final_<case>.frd",
    }
    if options.viz:
        try:
            result.pictures = _pictures(part, final, criteria, work, log)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            result.notes.append(f"pictures not written: {exc}")
    result.seconds = round(time.time() - started, 1)
    _keep_only(work, tag)
    (work / "result.json").write_text(json.dumps(result.to_dict(), indent=2))
    (work / "part.json").write_text(json.dumps(part_to_dict(part), indent=2))
    return result


def _displacement_row(name: str, case: str, value: float, limit: float, node: int, mesh: Mesh) -> Criterion:
    """A displacement criterion row."""
    where = tuple(round(c, 1) for c in mesh.nodes[node])
    util = value / limit
    return Criterion(
        name,
        case,
        round(value, 4),
        limit,
        "mm",
        round(util, 3),
        status_for(util),
        f"max at {where}",
    )


def _assumed_inputs(part: MaterialPart) -> list[str]:
    """Inputs that are assumptions, not measurements."""
    assert part.fem is not None
    items = part.assumed_inputs()
    items += [f"load case {c.name}: {c.source}" for c in part.fem.load_cases if c.assumed]
    items += [f"limit {lim.name}" for lim in part.fem.displacement_limits if lim.assumed]
    return items


def run_checks(
    parts: Mapping[str, MaterialPart],
    names: list[str],
    out_dir: Path,
    verdicts: Path | None,
    options: RunOptions = RunOptions(),  # noqa: B008
    log: Callable[[str], None] = print,
    record: bool = True,
) -> list[FemResult]:
    """Check the named parts (of ``parts``, the project's parts with a material), write reports
    and the verdicts file, print a summary."""
    from cadder.fem.report import file_hash, markdown, update_verdicts

    unknown = [n for n in names if n not in parts]
    if unknown:
        raise SystemExit(f"No material or FEM data: {', '.join(unknown)}. Defined: {', '.join(parts)}")
    targets: list[str] = []
    for name in names:
        base = parts[name].mirror_of
        if base:
            log(f"{name}: exact mirror image of {base}; its check applies")
        if (base or name) not in targets:
            targets.append(base or name)
    results = []
    for name in targets:
        log(f"{name}:")
        part = parts[name]
        try:
            result = analyze(part, out_dir, options, log)
        except (RuntimeError, applied.SpecError) as exc:
            log(f"  check could not be run: {exc}")
            result = FemResult(name, Status.INCONCLUSIVE, notes=[f"the check could not be run: {exc}"])
            (out_dir / name).mkdir(parents=True, exist_ok=True)
            (out_dir / name / "report.md").write_text(markdown(result))
            results.append(result)
            continue
        (out_dir / name / "report.md").write_text(markdown(result))
        if verdicts is not None and record:
            update_verdicts(verdicts, part, result, file_hash(out_dir / name / "part.stl"))
        results.append(result)
        log(f"  → {result.status.value}; report: {out_dir / name / 'report.md'}")
    return results
