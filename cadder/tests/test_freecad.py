"""FreeCAD assemblies: export (shared shapes, manifest) and, with FreeCAD, the build."""

import json
from pathlib import Path

import pytest
from demo.project import SLIDE
from pythonscad import cube

from cadder.freecad import Body, Component, FreeCadAssembly, Joint
from cadder.freecad.export import build_assembly, export_assembly, shared_name
from cadder.tools import find_tool


def _has_freecad() -> bool:
    try:
        find_tool("freecadcmd")
    except RuntimeError:
        return False
    return True


def test_congruent_components_share_one_stl(tmp_path: Path) -> None:
    manifest = json.loads(export_assembly(SLIDE, tmp_path, log=lambda _: None).read_text())
    entries = {c["name"]: c for c in manifest["components"]}
    assert entries["block_0"]["stl"] == entries["block_1"]["stl"] == "block"
    assert entries["block_1"]["center"][0] - entries["block_0"]["center"][0] == pytest.approx(20)
    assert sorted(p.name for p in (tmp_path / "Slide" / "stl").iterdir()) == [
        "block.stl",
        "plate.stl",
    ]
    assert manifest["joints"][0]["limits"] == [-5, 5]
    assert manifest["output"] == str(tmp_path / "Slide.FCStd")


def test_shared_name_prefers_the_components_shape() -> None:
    first = Component("motor_L", cube(1), "base", (0, 0, 0))
    assert shared_name(first, 2) == "motor"
    assert shared_name(Component("x_1", cube(1), "b", (0, 0, 0), shape="nema17"), 2) == "nema17"
    assert shared_name(first, 1) == "motor_L"


def test_assembly_is_checked_before_export(tmp_path: Path) -> None:
    broken = FreeCadAssembly(
        name="Broken",
        label="",
        description="",
        components=lambda: [Component("a", cube(1), "base", (0, 0, 0))],
        bodies=(Body("base", "a", grounded=True),),
        joints=lambda: [Joint("Slider", "a", "nope", (0, 0, 0), (1, 0, 0), "bad")],
    )
    with pytest.raises(ValueError, match="unknown component"):
        export_assembly(broken, tmp_path)


@pytest.mark.skipif(not _has_freecad(), reason="FreeCAD not installed")
def test_build_makes_an_fcstd_that_solves(tmp_path: Path) -> None:
    lines: list[str] = []
    manifest = export_assembly(SLIDE, tmp_path, log=lambda _: None)
    out = build_assembly(manifest, log=lines.append)
    assert out.is_file()
    # ground + Fixed block_1 + the slider
    assert lines[0] == "solve() -> 0; 3 components (1 shared shapes), 3 joints", lines
