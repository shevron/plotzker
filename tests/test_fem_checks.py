"""FEM checks of the plotter's parts and assembly checks."""

import pytest
from cadder.fem.evaluate import (
    Status,
)
from cadder.fem.runner import RunOptions, analyze
from cadder.tools import tools_available

from plotzker.parts import PARTS

needs_solvers = pytest.mark.skipif(not tools_available(), reason="gmsh and CalculiX not installed")


@needs_solvers
def test_real_part_runs_end_to_end(tmp_path):
    """The slider's verdict depends on assumed loads; the analysis itself must be sound."""
    options = RunOptions(project="plotzker.project:PROJECT")
    result = analyze(PARTS["x_idler_slider"], tmp_path, options, log=lambda _: None)
    assert all(c.ok for c in result.checks), [c.detail for c in result.checks if not c.ok]
    assert {c.case for c in result.criteria} == {"belt_preload", "belt_peak"}
    assert (tmp_path / "x_idler_slider" / "result.json").is_file()


def test_dovetail_play_tilt_follows_the_clearance_and_plate_length():
    import dataclasses

    from plotzker.params import TENSION_IDLER
    from plotzker.parts.tension_idler import dovetail_play

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
    from cadder.fem.assembly import check_assembly

    from plotzker.assembly_checks import tensioner_assembly
    from plotzker.params import TENSION_IDLER

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
    from plotzker.params import TENSION_IDLER
    from plotzker.parts.tension_idler import dovetail_play

    play = dovetail_play(TENSION_IDLER)
    # the play adds to the two deflections: each part is within its own 0.1, the pair is not
    assert by_name["idler_axle_vertical"].total == pytest.approx(0.18 + play.axle_vertical_mm)
    assert by_name["idler_axle_vertical"].status is Status.FAIL
    assert by_name["idler_axle_sideways"].total == pytest.approx(0.18)  # no play along the axle
    assert result.status is Status.FAIL


def test_floating_idlers_have_no_dovetail_play_term():
    from plotzker.assembly_checks import ASSEMBLY_CHECKS

    for assembly in ASSEMBLY_CHECKS.values():
        for limit in assembly.limits:
            assert all(term.part is not None for term in limit.terms)


def test_assembly_is_inconclusive_without_member_results(tmp_path):
    from cadder.fem.assembly import check_assembly

    from plotzker.assembly_checks import ASSEMBLY_CHECKS

    result = check_assembly(ASSEMBLY_CHECKS["x_idler_tensioner"], PARTS, tmp_path)
    assert result.status is Status.INCONCLUSIVE
    assert result.notes


def test_assembly_members_and_criteria_exist():
    from plotzker.assembly_checks import ASSEMBLY_CHECKS

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
