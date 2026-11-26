"""CPSK sketches load, solve and export to SVG as the spec (cadder/docs/cpsk) describes."""

import math
from dataclasses import astuple
from pathlib import Path

import pytest

from cadder import cpsk
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
    solved = cpsk.solve(cpsk.load(EXAMPLE), strict=True)
    assert solved.dof == 0
    assert solved.measured["diagonal"] == pytest.approx(math.hypot(40, 25))
    assert solved.primitive("hole").geometry == cpsk.Circle(20, 12.5, pytest.approx(25 / 6))


def test_example_overrides_change_derived_values():
    solved = cpsk.solve(cpsk.load(EXAMPLE, overrides={"width": "8cm", "height": 30}))
    assert solved.primitive("bottom").geometry.end == cpsk.Point(pytest.approx(80), pytest.approx(0))
    assert solved.primitive("hole").geometry.r == pytest.approx(5)


def test_example_svg_loads_as_a_plate_with_a_hole(tmp_path):
    svg = cpsk.to_svg(cpsk.solve(cpsk.load(EXAMPLE)))
    area, low, high = area_and_bounds(svg, tmp_path)
    assert low == pytest.approx([0, 0], abs=1e-6)
    assert high == pytest.approx([40, 25], abs=1e-6)
    assert area == pytest.approx(40 * 25 - math.pi * (25 / 6) ** 2, rel=1e-4)


# ----- Solving -----


def test_slot_of_lines_and_tangent_arcs(tmp_path):
    """A slot: two lines joined by two half-circle arcs, tangent at the joints."""
    solved = cpsk.solve(
        cpsk.loads(
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
        ),
        strict=True,
    )
    assert solved.dof == 0
    right = solved.primitive("right").geometry
    assert isinstance(right, cpsk.Arc)
    assert right.center == cpsk.Point(pytest.approx(20), pytest.approx(0, abs=1e-9))
    assert math.degrees(right.sweep) == pytest.approx(180)
    area, low, high = area_and_bounds(cpsk.to_svg(solved), tmp_path)
    assert area == pytest.approx(20 * 10 + math.pi * 25, rel=1e-4)
    # Negative coordinates: load_sketch puts the viewBox's bottom-left corner, (-5, -5), at 0.
    assert low == pytest.approx([0, 0], abs=1e-6)
    assert high == pytest.approx([30, 10], abs=1e-6)


def test_nested_and_top_level_forms_are_equivalent():
    nested = cpsk.solve(cpsk.loads(doc(RECTANGLE)))
    flat = cpsk.solve(
        cpsk.loads(
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
        )
    )
    assert nested.dof == flat.dof == 0
    for a, b in zip(nested.primitives, flat.primitives, strict=True):
        assert astuple(a.geometry) == pytest.approx(astuple(b.geometry))
    assert nested.primitive("t").geometry.end == cpsk.Point(pytest.approx(0), pytest.approx(20))


def test_document_units_apply_to_coordinates_and_svg(tmp_path):
    text = doc(
        RECTANGLE.replace('value="30"', 'value="3"').replace('value="20"', 'value="20mm"'),
        unit_length="cm",
    )
    solved = cpsk.solve(cpsk.loads(text))
    assert solved.primitive("t").geometry.start == cpsk.Point(pytest.approx(3), pytest.approx(2))
    _, _, high = area_and_bounds(cpsk.to_svg(solved), tmp_path)
    assert high == pytest.approx([30, 20], abs=1e-6)


def test_angles_and_measured_values():
    solved = cpsk.solve(
        cpsk.loads(
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
        )
    )
    a, b = solved.primitive("a").geometry, solved.primitive("b").geometry
    assert math.degrees(math.atan2(a.y2, a.x2)) == pytest.approx(30)
    assert math.degrees(math.atan2(b.y2, b.x2)) == pytest.approx(90)
    assert solved.measured["dx"] == pytest.approx(b.x2 - a.x2)


def test_block_keeps_stored_coordinates():
    solved = cpsk.solve(
        cpsk.loads(
            doc("""
        <geometry>
          <circle id="c" cx="3" cy="4" r="2"><block/></circle>
          <point id="p" x="9" y="9"><coincident b="c.center"/></point>
        </geometry>
        """)
        ),
        strict=True,
    )
    assert solved.primitive("c").geometry == cpsk.Circle(3, 4, 2)
    assert solved.primitive("p").geometry == cpsk.Point(pytest.approx(3), pytest.approx(4))


def test_solve_warnings_and_strict_mode():
    under = cpsk.loads(doc('<geometry><line x1="0" y1="0" x2="1" y2="0"><horizontal/></line></geometry>'))
    solved = cpsk.solve(under)
    assert solved.dof == 3
    assert {d.code for d in solved.warnings} == {"degrees-of-freedom"}
    with pytest.raises(cpsk.CpskSolveError):
        cpsk.solve(under, strict=True)

    redundant = cpsk.loads(doc(RECTANGLE.replace("<vertical/>\n  </line>", "<vertical/><vertical/>\n  </line>")))
    assert "redundant" in {d.code for d in cpsk.solve(redundant).warnings}


def test_conflicting_constraints_are_named():
    text = doc(RECTANGLE.replace('<distance value="h"/>', '<distance value="h"/><distance id="bad" value="25"/>'))
    with pytest.raises(cpsk.CpskSolveError) as info:
        cpsk.solve(cpsk.loads(text))
    assert codes(info.value) == {"conflicting"}
    assert any("'bad'" in id for d in info.value.diagnostics for id in d.ids)


# ----- Export -----


def test_open_wire_is_an_export_error_unless_allowed():
    solved = cpsk.solve(cpsk.loads(doc('<geometry><line x1="0" y1="0" x2="10" y2="0"/></geometry>')))
    with pytest.raises(cpsk.CpskExportError) as info:
        cpsk.to_svg(solved)
    assert codes(info.value) == {"open-wire"}
    assert 'fill="none"' in cpsk.to_svg(solved, allow_open=True)


def test_construction_geometry_is_not_exported():
    solved = cpsk.solve(
        cpsk.loads(
            doc(
                '<geometry><line construction="true" x1="0" y1="0" x2="10" y2="0"/>'
                '<circle cx="5" cy="5" r="1"/></geometry>'
            )
        )
    )
    svg = cpsk.to_svg(solved)
    assert svg.count(" A ") == 2 and " L " not in svg


# ----- Formulas -----


# ----- Structure, identifiers and nesting -----


def test_nested_constraint_in_anonymous_primitive():
    sketch = cpsk.loads(doc('<geometry><circle cx="0" cy="0" r="2"><diameter value="3"/></circle></geometry>'))
    assert cpsk.solve(sketch).primitives[0].geometry.r == pytest.approx(1.5)
