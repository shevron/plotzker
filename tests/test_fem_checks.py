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
    result = analyze(PARTS["idler_slider"], tmp_path, options, log=lambda _: None)
    assert all(c.ok for c in result.checks), [c.detail for c in result.checks if not c.ok]
    assert {c.case for c in result.criteria} == {"belt_preload", "belt_peak"}
    assert (tmp_path / "idler_slider" / "result.json").is_file()


def _write_result(folder, criteria):
    import json

    folder.mkdir(parents=True)
    rows = [{"name": n, "case": c, "value": v} for n, c, v in criteria]
    (folder / "result.json").write_text(json.dumps({"criteria": rows}))


def test_assembly_sums_member_deflections(tmp_path):
    from cadder.fem.assembly import check_assembly

    from plotzker.assembly_checks import tensioner_assembly

    assembly = tensioner_assembly(
        "sum_test", "", "y_idler_mount_left", "idler_slider", "idler_seat"
    )
    # each part alone is within its own 0.1 mm (the slider's and mount's limit names differ)
    for part, prefix in (
        ("idler_slider", "idler_axle"),
        ("y_idler_mount_left", "idler_seat"),
    ):
        _write_result(
            tmp_path / part,
            [
                (f"{prefix}_{d}", "belt_preload", 0.09)
                for d in ("along_belt", "sideways", "vertical")
            ],
        )
    result = check_assembly(assembly, PARTS, tmp_path)
    by_name = {r.name: r for r in result.rows}
    # the two deflections add up: 0.18 mm, within the sum of the two 0.1 mm limits
    assert by_name["idler_axle_vertical"].total == pytest.approx(0.18)
    assert by_name["idler_axle_vertical"].status is not Status.FAIL


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
