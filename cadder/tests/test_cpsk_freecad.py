"""The CPSK FreeCAD plugin: export (plan phase 2) and import (phase 3).

Without FreeCAD: expression translation both ways, the mapping of every case in
``cpsk_freecad/`` from plain data, and round trips through the plugin's plain data. With FreeCAD
(``freecadcmd``; skipped otherwise): every case is built and solved in FreeCAD and exported, and
``cadder.cpsk`` must solve each export to FreeCAD's geometry (plan §8, cross-solver check); each
export is imported into FreeCAD and exported again, which must give the same file (R5, D4).
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
from cpsk_core import Comment, CpskExportError, CpskLoadError, Document
from cpsk_core.document import parse, read
from cpsk_core.formula import parse as parse_formula
from cpsk_freecad import FREECAD_NAMESPACE, from_document, to_document
from cpsk_freecad.expressions import Path as FcPath
from cpsk_freecad.expressions import UnsupportedExpressionError, to_freecad, translate
from cpsk_freecad.sketch_data import Constraint, Geometry, SketchData, Variable, VarSet

CASES_DIR = Path(__file__).parent / "cpsk_freecad"
sys.path.insert(0, str(CASES_DIR))
from cases import C  # noqa: E402
from export_cases import X  # noqa: E402

ALL = C + X
SAMPLES = [
    Path(__file__).parents[1] / "docs" / "cpsk" / "examples" / "plate-with-hole.cpsk",
    CASES_DIR / "import" / "units-as-names.cpsk",
]
FREECAD_UNITS = {"t", "h", "s", "g", "e", "m", "min", "l"}
"""Some names FreeCAD's expressions read as units or constants (for tests without FreeCAD)."""
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
        ("min(Vars.width; 3 mm) / 3", "min(width, 3mm) / 3"),  # as FreeCAD stores it
        ("2 ^ -1", "2^-1"),
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
            VarSet(name, label, tuple(Variable(*p) for p in props)) for name, label, props in case.get("varsets", [])
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
    elements = (document.root, *document.root.descendants())
    values = (element.get("value") for element in elements if element.ours and element.get("id") == identifier)
    return next((value for value in values if value is not None), None)


def test_inactive_constraints_are_kept_in_the_extension_namespace() -> None:
    case = next(c for c in X if c["name"] == "inactive_constraint")
    document, _ = to_document(_data(case))
    text = document.write()
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


def _run_freecad(script: str, out: Path, **env: str) -> dict[str, Any]:
    freecadcmd = _freecadcmd()
    if freecadcmd is None:
        pytest.skip("FreeCAD not installed")
    root = Path(__file__).parents[1]
    paths = [root / "src", root / "freecad-addon" / "CPSK", CASES_DIR]
    run = subprocess.run(
        [str(freecadcmd), str(CASES_DIR / script)],
        capture_output=True,
        text=True,
        env={**os.environ, **env, "CPSK_PATHS": os.pathsep.join(map(str, paths))},
        check=False,
    )
    results = out / "results.json"
    assert results.is_file(), run.stdout + run.stderr
    return json.loads(results.read_text())  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def freecad_results(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    out = tmp_path_factory.mktemp("cpsk_export")
    return _run_freecad("run_export.py", out, CPSK_EXPORT_OUT=str(out))


@pytest.fixture(scope="module")
def imported_results(tmp_path_factory: pytest.TempPathFactory, freecad_results: dict[str, Any]) -> dict[str, Any]:
    out = tmp_path_factory.mktemp("cpsk_import")
    files = [r["file"] for r in freecad_results.values() if "file" in r] + list(map(str, SAMPLES))
    return _run_freecad("run_import.py", out, CPSK_IMPORT_IN=os.pathsep.join(files), CPSK_IMPORT_OUT=str(out))


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
            assert math.radians((a - b + 180) % 360 - 180) * ours[3] == pytest.approx(0, abs=tolerance)
    else:
        assert ours[1:] == pytest.approx(theirs[1:], abs=tolerance)


@pytest.mark.parametrize("case", ALL, ids=[c["name"] for c in ALL])
def test_freecad_export_solves_to_freecads_geometry(case: dict[str, Any], freecad_results: dict[str, Any]) -> None:
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


@pytest.mark.parametrize("case", EXPORTED, ids=[c["name"] for c in EXPORTED])
def test_freecad_round_trip_writes_the_same_file(
    case: dict[str, Any], freecad_results: dict[str, Any], imported_results: dict[str, Any]
) -> None:
    """FreeCAD → CPSK → FreeCAD → CPSK (R5): same geometry, constraints, names, expressions."""
    result = imported_results[case["name"]]
    assert set(result) >= {"file", "dof"}, result
    assert result["dof"] == 0
    assert result["import_warnings"] == []
    first = Path(freecad_results[case["name"]]["file"]).read_text()
    assert Path(result["file"]).read_text() == first


@pytest.mark.parametrize("path", SAMPLES, ids=[p.stem for p in SAMPLES])
def test_freecad_imports_documents_fully_constrained(path: Path, imported_results: dict[str, Any]) -> None:
    """CPSK → FreeCAD → CPSK (D4): fully constrained in FreeCAD, and the same file back."""
    result = imported_results[path.stem]
    assert set(result) >= {"file", "dof"}, result
    assert result["dof"] == 0
    assert all(code == "renamed" for code, _ in result["import_warnings"])
    assert Path(result["file"]).read_text() == _without_comments(read(path))


def test_freecad_renames_unit_names_and_export_restores_them(
    imported_results: dict[str, Any],
) -> None:
    result = imported_results["units-as-names"]
    assert sorted(ids[0] for _, ids in result["import_warnings"]) == ["e", "g", "s", "t"]
    properties = dict(result["varsets"][0][1])
    assert {"t_", "e_", "span", "tilt"} <= set(properties)
    assert properties["tilt"] == pytest.approx(-18)  # -(2^2) * 5 + 2^(3^0), FreeCAD's precedence
    assert ["Distance", "", True, False] in result["constraints"]  # the deactivated one


def test_freecad_file_menu_entry_points(tmp_path: Path) -> None:
    """Init.py registers .cpsk; importCPSK's open, insert and export work (phase 4)."""
    addon = Path(__file__).parents[1] / "freecad-addon" / "CPSK"
    results = _run_freecad(
        "run_entry_points.py",
        tmp_path,
        CPSK_ADDON=str(addon),
        CPSK_SAMPLE=str(SAMPLES[0]),
        CPSK_ENTRY_OUT=str(tmp_path),
    )
    # once, or twice when the addon is also installed in FreeCAD's Mod folder
    assert set(results["import_type"]) == set(results["export_type"]) == {"importCPSK"}
    assert results["inserted"] == ["Plate with a hole", 0, 0]
    assert results["opened"] == ["plate_with_hole"]
    assert "exactly one sketch" in results["refused"]
    assert (tmp_path / "export.cpsk").read_text() == _without_comments(read(SAMPLES[0]))


# ----- Import, without FreeCAD -----


def _without_comments(document: Document) -> str:
    document.prolog = []
    for element in (document.root, *document.root.descendants()):
        element.children = [child for child in element.children if not isinstance(child, Comment)]
    return document.write()


@pytest.mark.parametrize(
    ("cpsk_formula", "expected"),
    [
        ("width * 2", "Vars.width * 2"),
        ("-2^2", "-(2 ^ 2)"),
        ("2^3^2", "2 ^ (3 ^ 2)"),
        ("(-2)^2", "-2 ^ 2"),
        ("2^-1", "2 ^ -1"),
        ("min(width, 3mm) / 3", "min(Vars.width; 3 mm) / 3"),
        ("2.5cm + 1in", "2.5 cm + 1 in"),
        ("30deg", "30 °"),
        ("pi / 6", "pi / 6"),
        ("1 - (2 - 3)", "1 - (2 - 3)"),
    ],
)
def test_formulas_translate_to_freecad(cpsk_formula: str, expected: str) -> None:
    assert to_freecad(cpsk_formula, lambda name: f"Vars.{name}", _DIMENSIONS.get) == expected
    back = translate(expected, lambda path: path.parts[-1])
    assert parse_formula(back) == parse_formula(cpsk_formula)


_DIMENSIONS = {"width": "length", "tilt": "angle"}


@pytest.mark.parametrize(
    ("cpsk_formula", "expected"),
    [
        ("width - 6", "Vars.width - 6 mm"),
        ("-6 + width", "-6 mm + Vars.width"),
        ("width / 2 + 1", "Vars.width / 2 + 1 mm"),
        ("(1 + 2) + width", "(1 + 2) * 1 mm + Vars.width"),
        ("min(width, 3)", "min(Vars.width; 3 mm)"),
        ("tilt + 5", "Vars.tilt + 5 °"),
        ("width * 2 + 1cm", "Vars.width * 2 + 1 cm"),
        ("width * width + 4", "Vars.width * Vars.width + 4"),  # an area: left alone
        ("ratio + 1", "Vars.ratio + 1"),  # dimensionless
    ],
)
def test_unitless_numbers_in_sums_get_document_units(cpsk_formula: str, expected: str) -> None:
    """FreeCAD checks units in sums; a unitless number in a mm/deg document means mm or °."""
    assert to_freecad(cpsk_formula, lambda name: f"Vars.{name}", _DIMENSIONS.get) == expected


@pytest.mark.parametrize("path", SAMPLES, ids=[p.stem for p in SAMPLES])
def test_documents_round_trip_without_freecad(path: Path) -> None:
    data, _ = from_document(read(path), is_unit=FREECAD_UNITS.__contains__)
    document, _ = to_document(data)
    assert document.write() == _without_comments(read(path))


@pytest.mark.parametrize("case", EXPORTED, ids=[c["name"] for c in EXPORTED])
def test_freecad_cases_round_trip_without_freecad(case: dict[str, Any]) -> None:
    first, _ = to_document(_data(case))
    data, _ = from_document(parse(first.write()), is_unit=FREECAD_UNITS.__contains__)
    second, _ = to_document(data)
    assert second.write() == first.write()


def test_import_renames_unit_names_where_freecad_needs_them() -> None:
    data, warnings = from_document(
        read(CASES_DIR / "import" / "units-as-names.cpsk"), is_unit=FREECAD_UNITS.__contains__
    )
    assert sorted(w.ids[0] for w in warnings if w.code == "renamed") == ["e", "g", "s", "t"]
    assert [v.name for v in data.varsets[0].variables] == ["t_", "e_", "span", "tilt"]
    assert data.varsets[0].variables[2].expression == "t_ * e_ + 1 cm"
    assert data.expressions["cpsk_3"] == "Constraints.s_ - 6 mm"  # an anonymous constraint
    assert data.kept.formulas["c:cpsk_3"] == ("Constraints.s_ - 6 mm", "s - 6")
    assert data.kept.names == {"t_": "t", "e_": "e", "s_": "s", "g_": "g"} | {f"cpsk_{n}": "" for n in (1, 2, 3)}


def _document(body: str, units: str = "") -> Document:
    return parse(f'<sketch xmlns="{cpsk.NAMESPACE}" version="0.1"{units}>{body}</sketch>'.encode())


def test_import_needs_millimetres_and_degrees() -> None:
    with pytest.raises(CpskLoadError, match="only mm documents"):
        from_document(_document("", ' unit-length="cm"'))


def test_import_refuses_variables_and_constraints_that_use_each_other() -> None:
    body = """
      <variables><variable id="half" type="length" value="w / 2"/>
        <variable id="len" type="length" value="10"/></variables>
      <geometry><line x1="0" y1="0" x2="10" y2="0"><distance id="w" value="len"/></line>
      </geometry>"""
    with pytest.raises(CpskLoadError, match="circular dependency") as raised:
        from_document(_document(body))
    assert [d.ids for d in raised.value.diagnostics] == [("half",)]
