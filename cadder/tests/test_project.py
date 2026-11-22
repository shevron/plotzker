"""Projects, the part classes and the command line, on the demo project."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from demo.project import BLOCK, LIBRARY, PLATE, PROJECT, TAG
from typer.testing import CliRunner

from cadder.checks import DesignError
from cadder.cli import make_app
from cadder.part import MaterialPart, Part, PrintedPart, part_to_dict
from cadder.project import Project, find_spec, load_project

FIXTURE = Path(__file__).parent / "fixture"


def test_project_is_found_from_pyproject() -> None:
    assert find_spec(FIXTURE / "src" / "demo") == "demo.project:PROJECT"
    assert load_project("demo.project:PROJECT") is PROJECT
    with pytest.raises(TypeError):
        load_project("demo.project:LIBRARY")


def test_design_checks_raise_one_error_with_every_failure() -> None:
    def checks() -> list[tuple[bool, str]]:
        return [(False, "first"), (True, "fine"), (False, "second")]

    bad = Project(name="bad", spec="", root=FIXTURE, parts=dict, design_checks=checks)
    with pytest.raises(DesignError, match="first\n  second"):
        bad.check_design()


def test_printed_part_axis_is_its_build_direction() -> None:
    assert BLOCK.material_axis == (0, 0, 1)
    assert isinstance(BLOCK, MaterialPart) and isinstance(BLOCK, Part)
    data = part_to_dict(BLOCK)
    assert data["frame"] == "print"
    assert data["build_direction"] == [0, 0, 1]
    assert data["profile"]["name"] == "default"  # type: ignore[index]


def test_material_part_without_profile_uses_the_solid_values() -> None:
    data = part_to_dict(PLATE)
    assert "profile" not in data and data["material_axis"] is None
    steel = LIBRARY.material("steel")
    assert data["effective_properties"]["e_in_plane_mpa"] == steel.e_in_plane_mpa  # type: ignore[index]
    assert PLATE.axis == (0.0, 0.0, 1.0)


def test_plain_part_has_no_fem_data() -> None:
    assert part_to_dict(TAG) == {
        "name": "tag",
        "description": "A printed tag",
        "units": "mm, N, MPa, degrees, mm/s²; displacement and loads in the analysis frame",
        "fem_status": "no material or FEM data yet",
    }


def test_installed_frame_needs_its_own_geometry() -> None:
    with pytest.raises(ValueError, match="installed"):
        PrintedPart(
            name="x",
            description="",
            build=BLOCK.build,
            frame="installed",
            build_direction=(0, 0, 1),
            profile=BLOCK.profile,
            material=BLOCK.material,
        )


def test_cli_exports_parts_marked_for_stl(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(make_app(PROJECT), ["stl", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in tmp_path.iterdir()) == ["block.stl", "tag.stl"]


def test_cli_lists_and_describes_parts() -> None:
    runner = CliRunner()
    app = make_app(PROJECT)
    listing = runner.invoke(app, ["part", "--list"]).output
    assert "block" in listing and "default/petg" in listing
    assert "(no material or FEM data yet)" in listing
    data = json.loads(runner.invoke(app, ["part", "block", "--json"]).output)
    assert data["fem"]["load_cases"][0]["name"] == "push"
    assert "Design checks passed." in runner.invoke(app, ["check"]).output


def test_cadder_command_finds_the_project_in_its_folder() -> None:
    env_path = str(FIXTURE / "src")
    result = subprocess.run(
        [sys.executable, "-m", "cadder", "part", "--list"],
        cwd=FIXTURE,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": env_path, "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "block" in result.stdout
