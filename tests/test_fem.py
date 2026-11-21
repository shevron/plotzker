"""The FEM runner against closed-form results, and its building blocks."""

import math

import pytest
from pythonscad import cube, export

from plotter_cad.fem.applied import force_on_region, moment_on_region, net_force
from plotter_cad.fem.ccx import Supports, local_axes
from plotter_cad.fem.evaluate import (
    Status,
    Strengths,
    failure_index,
    status_for,
    worst,
)
from plotter_cad.fem.mesh import Mesh, TriFace, cover_region, covered_weights
from plotter_cad.fem.report import spec_hash, status_lines
from plotter_cad.fem.runner import RunOptions, analyze
from plotter_cad.fem.solve import proportional
from plotter_cad.fem.stl import clean_stl
from plotter_cad.fem.tools import tools_available
from plotter_cad.materials import load_material
from plotter_cad.part import (
    DisplacementLimit,
    FemSpec,
    Force,
    LoadCase,
    Part,
    Support,
    effective_properties,
)
from plotter_cad.parts import PARTS
from plotter_cad.print_profile import load_profile
from plotter_cad.regions import Box, Cylinder, Placement

needs_solvers = pytest.mark.skipif(not tools_available(), reason="gmsh and CalculiX not installed")

L, W, H = 100.0, 10.0, 5.0
LOAD_N = 1.0


def beam_part(build_direction: tuple[float, float, float]) -> Part:
    """A cantilever along x, fixed at x = 0, loaded by LOAD_N down at the free end."""
    spec = FemSpec(
        load_cases=(
            LoadCase(
                "tip",
                "",
                (
                    Force(
                        Box((L - 0.5, -1, -1), (L + 0.5, W + 1, H + 1), facing=(1, 0, 0)),
                        (0, 0, -LOAD_N),
                    ),
                ),
                "test",
            ),
        ),
        supports=(
            Support("wall", Box((-0.5, -1, -1), (0.5, W + 1, H + 1), facing=(-1, 0, 0)), ""),
        ),
        displacement_limits=(
            DisplacementLimit(
                "tip", Box((L - 0.5, -1, -1), (L + 0.5, W + 1, H + 1)), 5.0, (0, 0, 1)
            ),
        ),
    )
    return Part(
        "beam", "test beam", lambda: cube([L, W, H]), "installed", build_direction, fem=spec
    )


def expected_tip(modulus_along_beam: float, shear_modulus: float) -> float:
    """Timoshenko tip deflection of the beam."""
    inertia = W * H**3 / 12
    bending = LOAD_N * L**3 / (3 * modulus_along_beam * inertia)
    shear = LOAD_N * L / (5 / 6 * shear_modulus * W * H)
    return bending + shear


@needs_solvers
@pytest.mark.parametrize(
    ("build", "modulus"),
    [((0, 0, 1), "e_in_plane_mpa"), ((1, 0, 0), "e_build_mpa")],
    ids=["layers flat", "layers across the beam"],
)
def test_cantilever_matches_timoshenko(tmp_path, build, modulus):
    stl = tmp_path / "beam.stl"
    export(cube([L, W, H]), str(stl))
    result = analyze(
        beam_part(build),
        tmp_path,
        RunOptions(size=4.0, refine="always", graded=False),
        log=lambda _: None,
        stl=stl,
    )
    eff = effective_properties(load_material("petg"), load_profile())
    expected = expected_tip(eff[modulus], eff["g_build_mpa"])
    tip = next(c for c in result.criteria if c.name == "tip")
    assert tip.value == pytest.approx(expected, rel=0.03)
    assert all(c.ok for c in result.checks), [c.detail for c in result.checks if not c.ok]


def test_clean_stl_drops_slivers_and_makes_normals_outward(tmp_path):
    src = tmp_path / "a.stl"
    export(cube(10), str(src))
    text = src.read_text()
    sliver = (
        "facet normal 0 0 0\nouter loop\nvertex 0 0 0\nvertex 5 0 0\nvertex 10 0 0\n"
        "endloop\nendfacet\n"
    )
    src.write_text(text.replace("endsolid", sliver + "endsolid", 1))
    clean = clean_stl(src, tmp_path / "b.stl")
    assert clean.dropped >= 1
    assert clean.volume_mm3 == pytest.approx(1000)


def test_local_axes_are_orthonormal_with_the_build_direction_last():
    for build in [(0, 0, 1), (1, 0, 0), (0.3, -0.5, 0.8)]:
        e1, e2, e3 = local_axes(build)
        for a, b in [(e1, e2), (e1, e3), (e2, e3)]:
            assert sum(x * y for x, y in zip(a, b, strict=True)) == pytest.approx(0, abs=1e-12)
        n = math.sqrt(sum(c * c for c in build))
        assert e3 == pytest.approx(tuple(c / n for c in build))


def test_failure_index_of_simple_states():
    allow = Strengths(in_plane=20.0, build=10.0, shear_build=10.0)
    fi, mode = failure_index((10, 0, 0, 0, 0, 0), (0, 0, 1), allow)
    assert (fi, mode) == (pytest.approx(0.5), "in-plane")
    fi, mode = failure_index((0, 0, 8, 0, 0, 0), (0, 0, 1), allow)
    assert (fi, mode) == (pytest.approx(0.8), "interlayer")
    fi, _ = failure_index((0, 0, -8, 0, 0, 0), (0, 0, 1), allow)
    assert fi == pytest.approx(0.0)  # compression across the layers is not an interlayer failure
    fi, mode = failure_index((8, 0, 0, 0, 0, 0), (1, 0, 0), allow)
    assert (fi, mode) == (pytest.approx(0.8), "interlayer")  # x is the build direction here


def test_status_thresholds_and_worst():
    assert status_for(0.5) is Status.PASS
    assert status_for(0.9) is Status.MARGINAL
    assert status_for(1.2) is Status.FAIL
    assert worst([Status.PASS, Status.FAIL, Status.MARGINAL]) is Status.FAIL
    assert worst([Status.FAIL, Status.INCONCLUSIVE]) is Status.INCONCLUSIVE


def _plate_mesh() -> Mesh:
    """Two triangles of a unit-ish square plate in z = 0, facing +z, with mid-edge nodes."""
    nodes = {
        1: (0.0, 0.0, 0.0),
        2: (10.0, 0.0, 0.0),
        3: (10.0, 10.0, 0.0),
        4: (0.0, 10.0, 0.0),
        5: (5.0, 0.0, 0.0),
        6: (10.0, 5.0, 0.0),
        7: (5.0, 5.0, 0.0),
        8: (0.0, 5.0, 0.0),
        9: (5.0, 10.0, 0.0),
    }
    faces = [
        TriFace((1, 2, 3, 5, 6, 7), (20 / 3, 10 / 3, 0), (0, 0, 1), 50.0),
        TriFace((1, 3, 4, 7, 9, 8), (10 / 3, 20 / 3, 0), (0, 0, 1), 50.0),
    ]
    return Mesh(nodes, [], faces, 5.0)


def test_force_and_couple_distribution_are_exact():
    mesh, region = _plate_mesh(), Box((-1, -1, -1), (11, 11, 1))
    forces = force_on_region(mesh, region, (3.0, 0.0, -6.0), "test")
    assert [sum(f[i] for f in forces.values()) for i in range(3)] == pytest.approx([3, 0, -6])
    couple = moment_on_region(mesh, region, (0.0, 0.0, 12.0), "test")
    assert [sum(f[i] for f in couple.values()) for i in range(3)] == pytest.approx(
        [0, 0, 0], abs=1e-9
    )
    torque = sum(mesh.nodes[n][0] * f[1] - mesh.nodes[n][1] * f[0] for n, f in couple.items())
    assert torque == pytest.approx(12.0)


def test_net_force_ignores_loads_on_constrained_directions():
    forces = {1: (3.0, 4.0, 5.0), 2: (1.0, 1.0, 1.0)}
    supports = [Supports(frozenset({1}), (True, False, False))]
    assert net_force(forces, supports) == (1.0, 5.0, 6.0)


@needs_solvers
def test_real_part_runs_end_to_end(tmp_path):
    """The slider's verdict depends on assumed loads; the analysis itself must be sound."""
    result = analyze(PARTS["x_idler_slider"], tmp_path, log=lambda _: None)
    assert all(c.ok for c in result.checks), [c.detail for c in result.checks if not c.ok]
    assert {c.case for c in result.criteria} == {"belt_preload", "belt_peak"}
    assert (tmp_path / "x_idler_slider" / "result.json").is_file()


def test_covered_area_is_the_region_not_the_triangles():
    region = Box((2, 2, -1), (8, 8, 1), facing=(0, 0, 1))
    whole = Box((-1, -1, -1), (11, 11, 1))
    assert sum(covered_weights(cover_region(_plate_mesh(), whole)).values()) == pytest.approx(100.0)
    part = sum(covered_weights(cover_region(_plate_mesh(), region, n=24)).values())
    assert part == pytest.approx(36.0, rel=0.1)


def test_proportional_cases_are_detected():
    base = {1: (3.0, 0.0, 0.0), 2: (0.0, -4.0, 1.0)}
    assert proportional(base, {1: (4.5, 0.0, 0.0), 2: (0.0, -6.0, 1.5)}) == pytest.approx(1.5)
    assert proportional(base, {1: (3.0, 0.0, 0.0), 2: (0.0, -4.0, 2.0)}) is None
    assert proportional(base, {1: (3.0, 0.0, 0.0)}) is None


@needs_solvers
def test_a_far_from_limit_check_uses_one_mesh_and_one_solve(tmp_path):
    stl = tmp_path / "beam.stl"
    export(cube([L, W, H]), str(stl))
    part = beam_part((0, 0, 1))
    result = analyze(part, tmp_path, RunOptions(size=4.0, graded=False), lambda _: None, stl)
    assert result.mesh["solves"] == 1
    assert not any(c.name.startswith("convergence") for c in result.checks)


@needs_solvers
def test_viz_writes_pictures_and_a_vtu_for_every_load_case(tmp_path):
    stl = tmp_path / "beam.stl"
    export(cube([L, W, H]), str(stl))
    options = RunOptions(size=4.0, graded=False, viz=True)
    result = analyze(beam_part((0, 0, 1)), tmp_path, options, log=lambda _: None, stl=stl)
    assert not [n for n in result.notes if n.startswith("pictures not written")], result.notes
    names = {p.split("/")[-1] for p in result.pictures}
    assert {"tip_utilization.png", "tip_displacement.png", "tip_hotspot.png", "tip.vtu"} <= names
    assert all((tmp_path / "beam" / p).stat().st_size > 1000 for p in result.pictures)


def test_placement_turns_vectors_boxes_and_cylinders():
    place = Placement(1, (10.0, 0.0, 0.0))
    assert place.vector((1, 0, 0)) == (0, 1, 0)
    assert place.vector((0, 1, 0)) == (-1, 0, 0)
    assert place.point((1, 2, 3)) == (8, 1, 3)
    box = place.region(Box((0, 0, 0), (2, 1, 1), facing=(1, 0, 0)))
    assert (box.lo, box.hi, box.facing) == ((9, 0, 0), (10, 2, 1), (0, 1, 0))
    cyl = place.region(Cylinder((1, 0, 0), (0, 1, 0), 1, 2))
    assert (cyl.center, cyl.axis) == ((10, 1, 0), (1, 0, 0))


def test_bearing_load_weights_faces_by_the_cosine_of_their_angle():
    nodes = {i: (float(i), 0.0, 0.0) for i in range(1, 13)}
    head_on = TriFace((1, 2, 3, 4, 5, 6), (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), 2.0)
    oblique = TriFace((7, 8, 9, 10, 11, 12), (2.0, 0.0, 0.0), (-0.5, 0.866025, 0.0), 2.0)
    mesh = Mesh(nodes, [], [head_on, oblique], 1.0)
    region = Box((0, -1, -1), (20, 1, 1))
    forces = force_on_region(mesh, region, (4.0, 0.0, 0.0), "test", bearing=True)
    on_head_on = sum(forces[n][0] for n in (1, 2, 3, 4, 5, 6))
    on_oblique = sum(forces[n][0] for n in (7, 8, 9, 10, 11, 12))
    assert on_head_on + on_oblique == pytest.approx(4.0)
    assert on_oblique / on_head_on == pytest.approx(0.5, rel=0.02)


def test_status_lines_flag_stale_and_missing_checks(tmp_path):
    part = beam_part((0, 0, 1))
    verdicts = tmp_path / "verdicts.toml"
    assert "never checked" in status_lines(["beam"], {"beam": part}, verdicts, False)[0]
    entry = (
        '[beam]\nverdict = "PASS"\ndate = "2026-01-01"\ngeometry = "x"\n'
        f'spec = "{spec_hash(part)}"\n'
    )
    verdicts.write_text(entry)
    assert "PASS (2026-01-01)" in status_lines(["beam"], {"beam": part}, verdicts, False)[0]
    verdicts.write_text(entry.replace(spec_hash(part), "old"))
    assert "STALE (spec changed" in status_lines(["beam"], {"beam": part}, verdicts, False)[0]
    assert "not yet defined" in status_lines(["other"], {}, verdicts, False)[0]


def test_dovetail_play_tilt_follows_the_clearance_and_plate_length():
    import dataclasses

    from plotter_cad.params import TENSION_IDLER
    from plotter_cad.parts.tension_idler import dovetail_play

    base = dovetail_play(TENSION_IDLER)
    assert base.tilt_rad == pytest.approx(base.play_mm / TENSION_IDLER.plate_len)
    tight = dovetail_play(dataclasses.replace(TENSION_IDLER, slide_gap=TENSION_IDLER.slide_gap / 2))
    assert tight.tilt_rad == pytest.approx(base.tilt_rad / 2)
    assert tight.axle_vertical_mm == pytest.approx(base.axle_vertical_mm / 2)


def _write_result(folder, criteria):
    import json

    folder.mkdir(parents=True)
    rows = [{"name": n, "case": c, "value": v} for n, c, v in criteria]
    (folder / "result.json").write_text(json.dumps({"criteria": rows}))


def test_assembly_sums_member_deflections_and_play(tmp_path):
    from plotter_cad.assembly_checks import tensioner_assembly
    from plotter_cad.fem.assembly import check_assembly
    from plotter_cad.params import TENSION_IDLER

    # a dovetail tensioner (the generic prototype) on the Y parts' names: the play adds a rigid term
    assembly = tensioner_assembly(
        "dovetail_test",
        "",
        "y_idler_mount_left",
        "y_idler_slider_left",
        "idler_seat",
        TENSION_IDLER,
    )
    # each part alone is within its own 0.1 mm (the slider's and mount's limit names differ)
    cases = ("belt_preload",)
    _write_result(
        tmp_path / "y_idler_slider_left",
        [
            (f"idler_axle_{d}", c, 0.09)
            for d in ("along_belt", "sideways", "vertical")
            for c in cases
        ],
    )
    _write_result(
        tmp_path / "y_idler_mount_left",
        [
            (f"idler_seat_{d}", c, 0.09)
            for d in ("along_belt", "sideways", "vertical")
            for c in cases
        ],
    )
    result = check_assembly(assembly, PARTS, tmp_path)
    by_name = {r.name: r for r in result.rows}
    from plotter_cad.params import TENSION_IDLER
    from plotter_cad.parts.tension_idler import dovetail_play

    play = dovetail_play(TENSION_IDLER)
    # the play adds to the two deflections: each part is within its own 0.1, the pair is not
    assert by_name["idler_axle_vertical"].total == pytest.approx(0.18 + play.axle_vertical_mm)
    assert by_name["idler_axle_vertical"].status is Status.FAIL
    assert by_name["idler_axle_sideways"].total == pytest.approx(0.18)  # no play along the axle
    assert result.status is Status.FAIL


def test_floating_idlers_have_no_dovetail_play_term():
    from plotter_cad.assembly_checks import ASSEMBLY_CHECKS

    for assembly in ASSEMBLY_CHECKS.values():
        for limit in assembly.limits:
            assert all(term.part is not None for term in limit.terms)


def test_assembly_is_inconclusive_without_member_results(tmp_path):
    from plotter_cad.assembly_checks import ASSEMBLY_CHECKS
    from plotter_cad.fem.assembly import check_assembly

    result = check_assembly(ASSEMBLY_CHECKS["x_idler_tensioner"], PARTS, tmp_path)
    assert result.status is Status.INCONCLUSIVE
    assert result.notes


def test_assembly_members_and_criteria_exist():
    from plotter_cad.assembly_checks import ASSEMBLY_CHECKS

    for assembly in ASSEMBLY_CHECKS.values():
        for member in assembly.members:
            assert member in PARTS, member
        for limit in assembly.limits:
            for term in limit.terms:
                if term.part is None:
                    continue
                base = PARTS[term.part].mirror_of or term.part
                spec = PARTS[base].fem
                assert spec is not None
                assert term.criterion in {lim.name for lim in spec.displacement_limits}
