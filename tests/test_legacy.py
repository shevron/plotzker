"""The legacy package stays out of the current machine, and what it keeps still builds."""

import ast
from pathlib import Path

from cadder.testing import bounding_box, connected_groups, flatten, shell_count, volume
from pythonscad import union

import plotzker
from plotzker.assemblies import baseboard
from plotzker.legacy.zrib.assembly import zrib_mount_assembly, zrib_mount_fit_check, zrib_mount_installed
from plotzker.legacy.zrib.guard import zrib_guard
from plotzker.legacy.zrib.hanger import zrib_hanger
from plotzker.legacy.zrib.params import design_checks


def test_active_code_never_imports_legacy():
    package = Path(plotzker.__file__).parent
    offenders = []
    for path in package.rglob("*.py"):
        if path.relative_to(package).parts[0] == "legacy":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                names = [f"{module}.{alias.name}" for alias in node.names]
            else:
                continue
            if any("legacy" in name.split(".") for name in names):
                offenders.append(f"{path.relative_to(package)}:{node.lineno}")
    assert offenders == []


def test_zrib_design_checks_pass():
    assert [message for passed, message in design_checks() if not passed] == []


def test_zrib_parts_are_printable():
    for part in (zrib_hanger(), zrib_guard()):
        assert shell_count(part) == 1
        assert volume(part) > 0
        assert abs(bounding_box(part)[0][2]) < 0.01  # rests on the print bed


def test_zrib_mount_holds_together_without_collisions():
    assert len(connected_groups(zrib_mount_fit_check())) == 1
    items = list(zrib_mount_assembly())
    for index, item in enumerate(items):
        for other in items[index + 1 :]:
            assert volume(item & other) < 0.5  # a screw and its nut meet in their facets


def test_zrib_mount_fits_between_the_runners():
    runners = union(*flatten(baseboard.runners()))
    assert volume(runners & union(*flatten(zrib_mount_installed()))) < 1e-6
