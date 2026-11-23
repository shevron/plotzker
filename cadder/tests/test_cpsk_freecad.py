"""The CPSK FreeCAD plugin's exporter (plan phase 2).

Without FreeCAD: expression translation, and the mapping of every case in ``cpsk_freecad/``
from plain data. With FreeCAD (``freecadcmd``; skipped otherwise): every case is built and solved
in FreeCAD and exported by the plugin, and ``cadder.cpsk`` must solve each export to FreeCAD's
geometry (plan §8, cross-solver check).
"""

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from cadder import cpsk
from cadder.tools import find_tool
from cpsk_core import CpskExportError, Document
from cpsk_core.document import write
from cpsk_freecad import FREECAD_NAMESPACE, to_document
from cpsk_freecad.expressions import Path as FcPath
from cpsk_freecad.expressions import UnsupportedExpressionError, translate
from cpsk_freecad.sketch_data import Constraint, Geometry, SketchData, Variable, VarSet

CASES_DIR = Path(__file__).parent / "cpsk_freecad"
sys.path.insert(0, str(CASES_DIR))
from cases import C  # noqa: E402
from export_cases import X  # noqa: E402

ALL = C + X
EXPORTED = [c for c in ALL if not c.get("refused")]
DIMENSIONAL = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}


# ----- Expressions -----


_NAMES = {
    (False, ("Vars", "width")): "width",
    (False, ("", "Constraints", "w")): "w",
    (False, ("Constraints", "w")): "w",
    (True, ("My vars", "ratio")): "ratio",
}


def _resolve(path: FcPath) -> str:
    try:
        return _NAMES[path.label, path.parts]
    except KeyError:
        raise UnsupportedExpressionError(f"no {path}") from None


@pytest.mark.parametrize(
    ("freecad", "expected"),
    [
        ("2.5 cm", "2.5cm"),
        ("1in + 2 mm", "1in + 2mm"),
        ("30 °", "30deg"),
        ("0.5 rad", "0.5rad"),
        (".5 + 1e1", ".5 + 1e1"),
        ("-2^2", "(-2)^2"),
        ("-(2^2)", "-2^2"),
        ("2^3^2", "(2^3)^2"),
        ("2^(3^2)", "2^3^2"),
        ("2^-1", "2^-1"),
        ("(1 + 2) * 3", "(1 + 2) * 3"),
        ("1 - (2 - 3)", "1 - (2 - 3)"),
        ("(1 - 2) - 3", "1 - 2 - 3"),
        ("8 / (2 * 2)", "8 / (2 * 2)"),
        ("Vars.width*2", "width * 2"),
        (".Constraints.w / 2", "w / 2"),
        ("Constraints.w / 2", "w / 2"),
        ("<<My vars>>.ratio", "ratio"),
        ("min(Vars.width, 3 mm) + atan2(1, 2)", "min(width, 3mm) + atan2(1, 2)"),
        ("10 mm * sin(30)", "10mm * sin(30)"),
        ("pi / 6", "pi / 6"),
    ],
)
def test_expressions_translate_to_formulas(freecad: str, expected: str) -> None:
    assert translate(freecad, _resolve) == expected


@pytest.mark.parametrize(
    ("freecad", "reason"),
    [
        ("1 > 0 ? 5 : 6", "'>' is not supported"),
        ("floor(1.5)", "function 'floor'"),
        ("2 ft", "unit 'ft'"),
        ("Spreadsheet.A1", "no Spreadsheet.A1"),
        ("e", "no .e"),
        ("2 *", "incomplete"),
        ("(2", "incomplete"),
    ],
)
def test_untranslatable_expressions_are_refused(freecad: str, reason: str) -> None:
    with pytest.raises(UnsupportedExpressionError, match=reason.replace("?", r"\?")):
        translate(freecad, _resolve)


# ----- Mapping, without FreeCAD -----


def _data(case: dict[str, Any]) -> SketchData:
    """A case as the snapshot FreeCAD would give (seed geometry, as built by run_export.py)."""
    geometry, constraints, expressions = [], [], {}
    for index, g in enumerate(case["geometry"]):
        kind, *rest = g
        coords = tuple(float(v) for v in rest if v != "block")
        geometry.append(Geometry(kind if kind != "ellipse" else "Ellipse", coords))
        if g[-1] == "block":
            constraints.append(Constraint("Block", index))
    for kind, args, value, driving, *more in case["constraints"]:
        extra = more[0] if more else {}
        number = 1.0 if value is None else float(value)
        if kind == "Angle":
            number = math.radians(number)
        operands = dict(zip(_FIELDS, _with_positions(kind, list(args)), strict=False))
        constraints.append(
            Constraint(
                kind,
                **operands,
                value=number if kind in DIMENSIONAL else 0.0,
                name=extra.get("name", ""),
                driving=driving,
                active=extra.get("active", True),
            )
        )
        if "expression" in extra:
            expressions[extra["name"]] = extra["expression"]
    return SketchData(
        geometry=geometry,
        external=[Geometry(g[0], tuple(map(float, g[1:])), True) for g in case.get("external", [])],
        constraints=constraints,
        expressions=expressions,
        varsets=[
            VarSet(name, label, tuple(Variable(*p) for p in props))
            for name, label, props in case.get("varsets", [])
        ],
    )


_FIELDS = ("first", "first_pos", "second", "second_pos", "third", "third_pos")


def _with_positions(kind: str, args: list[int]) -> list[int]:
    """Sketcher.Constraint's short argument forms → (GeoId, PosId) pairs."""
    if len(args) == 1:  # an edge
        return [args[0], 0]
    if len(args) == 2 and kind in {"DistanceX", "DistanceY"}:  # one point
        return args
    if len(args) == 2:  # two edges
        return [args[0], 0, args[1], 0]
    if len(args) in (3, 5):  # ends with an edge
        return [*args, 0]
    return args


@pytest.mark.parametrize("case", ALL, ids=[c["name"] for c in ALL])
def test_cases_map_without_freecad(case: dict[str, Any]) -> None:
    data = _data(case)
    if case.get("refused"):
        with pytest.raises(CpskExportError) as raised:
            to_document(data)
        assert [d.ids[0] for d in raised.value.diagnostics] == case["refused"]
        return
    document, _ = to_document(data)
    solved = cpsk.solve(cpsk.compile_document(document))
    assert solved.dof == 0
    for identifier, formula in case.get("formulas", {}).items():
        assert _value_of(document, identifier) == formula


def _value_of(document: Document, identifier: str) -> str | None:
    def walk(element: Any) -> Any:
        if element.get("id") == identifier:
            return element.get("value")
        for child in element.elements():
            found = walk(child)
            if found is not None:
                return found
        return None

    return walk(document.root)  # type: ignore[no-any-return]


def test_inactive_constraints_are_kept_in_the_extension_namespace() -> None:
    case = next(c for c in X if c["name"] == "inactive_constraint")
    document, _ = to_document(_data(case))
    text = write(document)
    assert f'xmlns:freecad="{FREECAD_NAMESPACE}"' in text
    assert '<freecad:inactive>\n      <distance id="old" of="edge2" value="7"/>' in text
    assert "old" not in {c.id for c in cpsk.compile_document(document).constraints}


def test_sketch_problems_are_warnings() -> None:
    data = SketchData(geometry=[Geometry("point", (1, 2))], dof=2, redundant=[1])
    data.constraints.append(Constraint("Block", 0))
    _, warnings = to_document(data)
    assert [(w.code, w.ids) for w in warnings] == [
        ("degrees-of-freedom", ()),
        ("redundant", ("Constraint1",)),
    ]


# ----- With FreeCAD: cross-solver check -----


def _freecadcmd() -> Path | None:
    try:
        return find_tool("freecadcmd")
    except RuntimeError:
        return None


@pytest.fixture(scope="module")
def freecad_results(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    freecadcmd = _freecadcmd()
    if freecadcmd is None:
        pytest.skip("FreeCAD not installed")
    out = tmp_path_factory.mktemp("cpsk_export")
    root = Path(__file__).parents[1]
    paths = [root / "src", root / "freecad-addon" / "CPSK", CASES_DIR]
    env = {
        **os.environ,
        "CPSK_EXPORT_OUT": str(out),
        "CPSK_PATHS": os.pathsep.join(map(str, paths)),
    }
    run = subprocess.run(
        [str(freecadcmd), str(CASES_DIR / "run_export.py")],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    results = out / "results.json"
    assert results.is_file(), run.stdout + run.stderr
    return json.loads(results.read_text())  # type: ignore[no-any-return]


def _dump(geometry: Any) -> list[Any]:
    match geometry:
        case cpsk.Point():
            return ["point", geometry.x, geometry.y]
        case cpsk.Line():
            return ["line", geometry.x1, geometry.y1, geometry.x2, geometry.y2]
        case cpsk.Circle():
            return ["circle", geometry.cx, geometry.cy, geometry.r]
    return ["arc", geometry.cx, geometry.cy, geometry.r, geometry.start_angle, geometry.end_angle]


def _assert_same(ours: list[Any], theirs: list[Any], tolerance: float = 1e-9) -> None:
    assert ours[0] == theirs[0]
    if ours[0] == "arc":
        center_radius = ours[1:4]
        assert center_radius == pytest.approx(theirs[1:4], abs=tolerance)
        for a, b in zip(ours[4:], theirs[4:], strict=True):  # same direction; radius ≤ 10 mm
            assert math.radians((a - b + 180) % 360 - 180) * ours[3] == pytest.approx(
                0, abs=tolerance
            )
    else:
        assert ours[1:] == pytest.approx(theirs[1:], abs=tolerance)


@pytest.mark.parametrize("case", ALL, ids=[c["name"] for c in ALL])
def test_freecad_export_solves_to_freecads_geometry(
    case: dict[str, Any], freecad_results: dict[str, Any]
) -> None:
    result = freecad_results[case["name"]]
    assert "crash" not in result, result.get("crash")
    if case.get("refused"):
        assert [ids[0] for ids, _ in result["errors"]] == case["refused"]
        return
    assert "errors" not in result, result.get("errors")
    solved = cpsk.solve(cpsk.load(result["file"]))
    assert solved.dof == result["dof"] == 0
    ours = [_dump(p.geometry) for p in solved.primitives if not p.id.startswith("external")]
    assert len(ours) == len(result["geometry"])
    for mine, theirs in zip(ours, result["geometry"], strict=True):
        _assert_same(mine, theirs)
