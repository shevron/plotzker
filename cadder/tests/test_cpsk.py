"""CPSK sketches load, solve and export to SVG as the spec (cadder/docs/cpsk) describes."""

import math
from dataclasses import astuple
from pathlib import Path

import pytest

from cadder import cpsk
from cadder.cpsk.formula import Units, evaluate, parse
from cadder.geometry import load_sketch

EXAMPLE = Path(__file__).parents[1] / "docs" / "cpsk" / "examples" / "plate-with-hole.cpsk"


def doc(body: str, **attrs: str) -> str:
    """A CPSK document around ``body``."""
    extra = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<sketch xmlns="{cpsk.NAMESPACE}" version="0.1"{extra}>{body}</sketch>'


def codes(error: cpsk.CpskError) -> set[str]:
    return {d.code for d in error.diagnostics}


def load_error(text: str, **overrides: float | str) -> set[str]:
    with pytest.raises(cpsk.CpskLoadError) as info:
        cpsk.loads(text, overrides)
    return codes(info.value)


def area_and_bounds(svg: str, tmp_path: Path) -> tuple[float, list[float], list[float]]:
    """Net area and bounding box of an SVG profile as ``load_sketch`` imports it."""
    path = tmp_path / "sketch.svg"
    path.write_text(svg)
    outlines = load_sketch(path, fn=720).mesh()
    area = sum(
        (a[0] * b[1] - b[0] * a[1]) / 2
        for outline in outlines
        for a, b in zip(outline, outline[1:] + outline[:1], strict=True)
    )
    points = [p for outline in outlines for p in outline]
    return (
        area,
        [min(p[i] for p in points) for i in (0, 1)],
        [max(p[i] for p in points) for i in (0, 1)],
    )


RECTANGLE = """
<variables>
  <variable id="w" type="length" value="30"/>
  <variable id="h" type="length" value="20"/>
</variables>
<geometry>
  <line id="b" x1="1" y1="-1" x2="28" y2="2">
    <coincident a="self.start" b="origin"/>
    <horizontal/>
    <distance value="w"/>
    <coincident a="self.end" b="r.start"/>
    <coincident a="self.start" b="l.end"/>
  </line>
  <line id="r" x1="29" y1="1" x2="31" y2="19">
    <vertical/>
    <distance value="h"/>
    <coincident a="self.end" b="t.start"/>
  </line>
  <line id="t" x1="30" y1="21" x2="-1" y2="19">
    <horizontal/>
    <coincident a="self.end" b="l.start"/>
  </line>
  <line id="l" x1="1" y1="20" x2="0" y2="1">
    <vertical/>
  </line>
</geometry>
"""


# ----- The spec example -----


def test_example_solves_fully_constrained():
    solved = cpsk.load(EXAMPLE).solve(strict=True)
    assert solved.dof == 0
    assert solved.measured["diagonal"] == pytest.approx(math.hypot(40, 25))
    assert solved.primitive("hole").geometry == cpsk.Circle(20, 12.5, pytest.approx(25 / 6))


def test_example_overrides_change_derived_values():
    solved = cpsk.load(EXAMPLE, overrides={"width": "8cm", "height": 30}).solve()
    assert solved.primitive("bottom").geometry.end == cpsk.Point(
        pytest.approx(80), pytest.approx(0)
    )
    assert solved.primitive("hole").geometry.r == pytest.approx(5)


def test_override_outside_limits():
    assert "limits" in load_error(EXAMPLE.read_text(), width=500)


def test_override_of_unknown_variable():
    assert "override" in load_error(EXAMPLE.read_text(), depth=5)


def test_example_svg_loads_as_a_plate_with_a_hole(tmp_path):
    svg = cpsk.to_svg(cpsk.load(EXAMPLE).solve())
    area, lo, hi = area_and_bounds(svg, tmp_path)
    assert lo == pytest.approx([0, 0], abs=1e-6)
    assert hi == pytest.approx([40, 25], abs=1e-6)
    assert area == pytest.approx(40 * 25 - math.pi * (25 / 6) ** 2, rel=1e-4)


# ----- Solving -----


def test_slot_of_lines_and_tangent_arcs(tmp_path):
    """A slot: two lines joined by two half-circle arcs, tangent at the joints."""
    solved = cpsk.loads(
        doc("""
        <geometry>
          <line id="bottom" x1="0" y1="-5.5" x2="21" y2="-4.5">
            <horizontal/>
            <distance value="20"/>
            <tangent a="self.end" b="right.start"/>
            <tangent a="self.start" b="left.end"/>
          </line>
          <arc id="right" cx="20" cy="0" r="5.5" start-angle="-85" end-angle="92">
            <radius value="5"/>
            <equal b="left"/>
            <tangent a="self.end" b="top.start"/>
          </arc>
          <line id="top" x1="20" y1="5" x2="0" y2="5.5">
            <tangent a="self.end" b="left.start"/>
          </line>
          <arc id="left" cx="0.5" cy="0" r="5" start-angle="88" end-angle="272">
            <coincident a="self.center" b="origin"/>
          </arc>
        </geometry>
        """)
    ).solve(strict=True)
    assert solved.dof == 0
    right = solved.primitive("right").geometry
    assert isinstance(right, cpsk.Arc)
    assert right.center == cpsk.Point(pytest.approx(20), pytest.approx(0, abs=1e-9))
    assert math.degrees(right.sweep) == pytest.approx(180)
    area, lo, hi = area_and_bounds(cpsk.to_svg(solved), tmp_path)
    assert area == pytest.approx(20 * 10 + math.pi * 25, rel=1e-4)
    # Negative coordinates: load_sketch puts the viewBox's bottom-left corner, (-5, -5), at 0.
    assert lo == pytest.approx([0, 0], abs=1e-6)
    assert hi == pytest.approx([30, 10], abs=1e-6)


def test_nested_and_top_level_forms_are_equivalent():
    nested = cpsk.loads(doc(RECTANGLE)).solve()
    flat = cpsk.loads(
        doc("""
        <variables>
          <variable id="w" type="length" value="30"/>
          <variable id="h" type="length" value="20"/>
        </variables>
        <geometry>
          <line id="b" x1="1" y1="-1" x2="28" y2="2"/>
          <line id="r" x1="29" y1="1" x2="31" y2="19"/>
          <line id="t" x1="30" y1="21" x2="-1" y2="19"/>
          <line id="l" x1="1" y1="20" x2="0" y2="1"/>
        </geometry>
        <constraints>
          <coincident a="b.start" b="origin"/>
          <horizontal of="b"/>
          <distance of="b" value="w"/>
          <coincident a="b.end" b="r.start"/>
          <coincident a="b.start" b="l.end"/>
          <vertical of="r"/>
          <distance of="r" value="h"/>
          <coincident a="r.end" b="t.start"/>
          <horizontal of="t"/>
          <coincident a="t.end" b="l.start"/>
          <vertical of="l"/>
        </constraints>
        """)
    ).solve()
    assert nested.dof == flat.dof == 0
    for a, b in zip(nested.primitives, flat.primitives, strict=True):
        assert astuple(a.geometry) == pytest.approx(astuple(b.geometry))
    assert nested.primitive("t").geometry.end == cpsk.Point(pytest.approx(0), pytest.approx(20))


def test_document_units_apply_to_coordinates_and_svg(tmp_path):
    text = doc(
        RECTANGLE.replace('value="30"', 'value="3"').replace('value="20"', 'value="20mm"'),
        unit_length="cm",
    )
    solved = cpsk.loads(text).solve()
    assert solved.primitive("t").geometry.start == cpsk.Point(pytest.approx(3), pytest.approx(2))
    _, _, hi = area_and_bounds(cpsk.to_svg(solved), tmp_path)
    assert hi == pytest.approx([30, 20], abs=1e-6)


def test_angles_and_measured_values():
    solved = cpsk.loads(
        doc("""
        <geometry>
          <line id="a" x1="0" y1="0" x2="10" y2="1">
            <coincident a="self.start" b="origin"/>
            <angle a="x_axis" value="30"/>
            <distance value="10"/>
          </line>
          <line id="b" x1="0" y1="0" x2="-1" y2="9">
            <coincident a="self.start" b="origin"/>
            <angle a="a" value="60deg"/>
            <distance value="10"/>
            <distance-x id="dx" a="a.end" b="self.end" driving="false"/>
          </line>
        </geometry>
        """)
    ).solve()
    a, b = solved.primitive("a").geometry, solved.primitive("b").geometry
    assert math.degrees(math.atan2(a.y2, a.x2)) == pytest.approx(30)
    assert math.degrees(math.atan2(b.y2, b.x2)) == pytest.approx(90)
    assert solved.measured["dx"] == pytest.approx(b.x2 - a.x2)


def test_block_keeps_stored_coordinates():
    solved = cpsk.loads(
        doc("""
        <geometry>
          <circle id="c" cx="3" cy="4" r="2"><block/></circle>
          <point id="p" x="9" y="9"><coincident b="c.center"/></point>
        </geometry>
        """)
    ).solve(strict=True)
    assert solved.primitive("c").geometry == cpsk.Circle(3, 4, 2)
    assert solved.primitive("p").geometry == cpsk.Point(pytest.approx(3), pytest.approx(4))


def test_solve_warnings_and_strict_mode():
    under = cpsk.loads(
        doc('<geometry><line x1="0" y1="0" x2="1" y2="0"><horizontal/></line></geometry>')
    )
    solved = under.solve()
    assert solved.dof == 3
    assert {d.code for d in solved.warnings} == {"degrees-of-freedom"}
    with pytest.raises(cpsk.CpskSolveError):
        under.solve(strict=True)

    redundant = cpsk.loads(
        doc(RECTANGLE.replace("<vertical/>\n  </line>", "<vertical/><vertical/>\n  </line>"))
    )
    assert "redundant" in {d.code for d in redundant.solve().warnings}


def test_conflicting_constraints_are_named():
    text = doc(
        RECTANGLE.replace(
            '<distance value="h"/>', '<distance value="h"/><distance id="bad" value="25"/>'
        )
    )
    with pytest.raises(cpsk.CpskSolveError) as info:
        cpsk.loads(text).solve()
    assert codes(info.value) == {"conflicting"}
    assert any("'bad'" in id for d in info.value.diagnostics for id in d.ids)


# ----- Export -----


def test_open_wire_is_an_export_error_unless_allowed():
    solved = cpsk.loads(doc('<geometry><line x1="0" y1="0" x2="10" y2="0"/></geometry>')).solve()
    with pytest.raises(cpsk.CpskExportError) as info:
        cpsk.to_svg(solved)
    assert codes(info.value) == {"open-wire"}
    assert 'fill="none"' in cpsk.to_svg(solved, allow_open=True)


def test_construction_geometry_is_not_exported():
    solved = cpsk.loads(
        doc(
            '<geometry><line construction="true" x1="0" y1="0" x2="10" y2="0"/>'
            '<circle cx="5" cy="5" r="1"/></geometry>'
        )
    ).solve()
    svg = cpsk.to_svg(solved)
    assert svg.count(" A ") == 2 and " L " not in svg


# ----- Formulas -----


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("-2^2", -4),
        ("2^3^2", 512),
        ("1 + 2 * 3", 7),
        ("(1 + 2) * 3", 9),
        ("2.5cm + 1 in", 50.4),
        ("sin(30)", 0.5),
        ("atan2(1, 1)", 45),
        ("min(3, 1, 2) + max(1, 4)", 5),
        ("1e1 / 4", 2.5),
    ],
)
def test_formula_values(formula, expected):
    assert evaluate(parse(formula), Units(), lambda name: 0.0) == pytest.approx(expected)


@pytest.mark.parametrize(
    "formula", ["1 +", "mm", "sin(1, 2)", "min(1)", "2 3", "(1", "a..b", "1 $ 2"]
)
def test_malformed_formulas(formula):
    assert load_error(doc(f'<variables><variable id="v" value="{formula}"/></variables>')) == {
        "formula"
    }


@pytest.mark.parametrize(
    ("variables", "code"),
    [
        ('<variable id="a" value="b"/><variable id="b" value="a + 1"/>', "cycle"),
        ('<variable id="a" value="nothing"/>', "reference"),
        ('<variable id="a" value="1 / 0"/>', "formula"),
        ('<variable id="a" value="sqrt(-1)"/>', "formula"),
        ('<variable id="a" type="length" value="30deg"/>', "unit"),
        ('<variable id="a" value="5mm"/>', "unit"),
    ],
)
def test_formula_errors(variables, code):
    assert code in load_error(doc(f"<variables>{variables}</variables>"))


def test_formulas_cannot_read_solved_values():
    body = """
    <variables><variable id="v" value="1"/></variables>
    <geometry>
      <line id="l" x1="0" y1="0" x2="1" y2="0">
        <distance id="meas" driving="false"/>
        <horizontal/>
      </line>
      <circle id="c" cx="0" cy="0" r="1"><radius value="{}"/></circle>
    </geometry>
    """
    assert load_error(doc(body.format("l.length"))) == {"forbidden-reference"}
    assert load_error(doc(body.format("meas"))) == {"forbidden-reference"}
    assert cpsk.loads(doc(body.format("v * 2"))).constraints[-1].value == 2


# ----- Structure, identifiers and nesting -----


@pytest.mark.parametrize("id", ["origin", "self", "pi", "sin", "mm", "x_axis"])
def test_reserved_words_are_not_identifiers(id):
    assert load_error(doc(f'<geometry><point id="{id}" x="0" y="0"/></geometry>')) == {"reserved"}


def test_duplicate_identifiers():
    body = (
        '<variables><variable id="a" value="1"/></variables>'
        '<geometry><point id="a" x="0" y="0"/></geometry>'
    )
    assert load_error(doc(body)) == {"duplicate-id"}


@pytest.mark.parametrize(
    ("constraint", "code"),
    [
        ('<constraints><horizontal a="self.start" b="l.end"/></constraints>', "self"),
        ('<constraints><radius of="l" value="1"/></constraints>', "operand"),
        ('<constraints><coincident a="l.center" b="origin"/></constraints>', "reference"),
        ('<constraints><coincident a="nope" b="origin"/></constraints>', "reference"),
        ('<constraints><coincident a="l.start.x" b="origin"/></constraints>', "reference"),
    ],
)
def test_constraint_errors(constraint, code):
    body = f'<geometry><line id="l" x1="0" y1="0" x2="1" y2="0"/></geometry>{constraint}'
    assert load_error(doc(body)) == {code}


@pytest.mark.parametrize(
    ("nested", "code"),
    [
        ('<coincident a="p.start" b="origin"/>', "nesting"),  # does not involve its parent
        ('<horizontal of="self"/>', "nesting"),
        ("<symmetric/>", "nesting"),
        ('<coincident b="origin"/>', "operand"),  # the parent line is not a point
        ('<radius value="1"/>', "operand"),
    ],
)
def test_nesting_errors(nested, code):
    body = f'<geometry><line id="p" x1="0" y1="0" x2="1" y2="0">{nested}</line></geometry>'
    assert load_error(doc(body)) == {code}


def test_nested_constraint_in_anonymous_primitive():
    sketch = cpsk.loads(
        doc('<geometry><circle cx="0" cy="0" r="2"><diameter value="3"/></circle></geometry>')
    )
    assert sketch.solve().primitives[0].geometry.r == pytest.approx(1.5)


def test_unknown_content_warns_and_extensions_are_ignored():
    sketch = cpsk.loads(
        doc(
            '<geometry xmlns:x="urn:example"><point x="0" y="0" x:note="hi" color="red"/>'
            "<x:thing/><spline/></geometry>"
        )
    )
    assert [d.code for d in sketch.warnings] == ["unknown-content", "unknown-content"]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        (doc("").replace('version="0.1"', 'version="0.2"'), "version"),
        (doc("").replace(' version="0.1"', ""), "structure"),
        (doc("<constraints/><geometry/>"), "structure"),
        ('<sketch version="0.1"/>', "structure"),
        (doc('<geometry><point x="1mm" y="0"/></geometry>'), "structure"),
        (doc("", unit_length="ft"), "unit"),
    ],
)
def test_document_errors(text, code):
    assert code in load_error(text)


def test_malformed_xml_reports_the_line():
    with pytest.raises(cpsk.CpskLoadError) as info:
        cpsk.loads(doc("\n<geometry>\n<point x='0'</geometry>"))
    (diagnostic,) = info.value.diagnostics
    assert diagnostic.code == "xml" and diagnostic.line == 3


def test_empty_containers_may_be_omitted():
    assert cpsk.loads(doc('<geometry><point x="0" y="0"/></geometry>')).constraints == ()
