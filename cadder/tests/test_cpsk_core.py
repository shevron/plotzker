"""CPSK documents parse, compile and write as the spec (cadder/docs/cpsk) describes.

Uses only cpsk_core, so it also runs on Python 3.11 (FreeCAD's): ``make test-cpsk-core``.
"""

from pathlib import Path

import pytest

import cpsk_core
from cpsk_core import document
from cpsk_core.formula import Units, evaluate, parse

EXAMPLE = Path(__file__).parents[1] / "docs" / "cpsk" / "examples" / "plate-with-hole.cpsk"


def doc(body: str, **attrs: str) -> str:
    """A CPSK document around ``body``."""
    extra = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<sketch xmlns="{cpsk_core.NAMESPACE}" version="0.1"{extra}>{body}</sketch>'


def codes(error: cpsk_core.CpskError) -> set[str]:
    return {d.code for d in error.diagnostics}


def load_error(text: str, **overrides: float | str) -> set[str]:
    with pytest.raises(cpsk_core.CpskLoadError) as info:
        cpsk_core.loads(text, overrides)
    return codes(info.value)


def test_override_outside_limits():
    assert "limits" in load_error(EXAMPLE.read_text(), width=500)


def test_override_of_unknown_variable():
    assert "override" in load_error(EXAMPLE.read_text(), depth=5)


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


@pytest.mark.parametrize("formula", ["1 +", "mm", "sin(1, 2)", "min(1)", "2 3", "(1", "a..b", "1 $ 2"])
def test_malformed_formulas(formula):
    assert load_error(doc(f'<variables><variable id="v" value="{formula}"/></variables>')) == {"formula"}


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
    assert cpsk_core.loads(doc(body.format("v * 2"))).constraints[-1].value == 2


@pytest.mark.parametrize("id", ["origin", "self", "pi", "sin", "mm", "x_axis"])
def test_reserved_words_are_not_identifiers(id):
    assert load_error(doc(f'<geometry><point id="{id}" x="0" y="0"/></geometry>')) == {"reserved"}


def test_duplicate_identifiers():
    body = '<variables><variable id="a" value="1"/></variables><geometry><point id="a" x="0" y="0"/></geometry>'
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


def test_unknown_content_warns_and_extensions_are_ignored():
    sketch = cpsk_core.loads(
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
    with pytest.raises(cpsk_core.CpskLoadError) as info:
        cpsk_core.loads(doc("\n<geometry>\n<point x='0'</geometry>"))
    (diagnostic,) = info.value.diagnostics
    assert diagnostic.code == "xml" and diagnostic.line == 3


def test_empty_containers_may_be_omitted():
    assert cpsk_core.loads(doc('<geometry><point x="0" y="0"/></geometry>')).constraints == ()


# ----- The lossless document and the canonical writer -----


def test_example_is_canonical():
    """The spec example reads and writes back unchanged (plan phase 1)."""
    text = EXAMPLE.read_text()
    assert document.parse(text).write() == text


def test_round_trip_keeps_comments_extensions_and_unknown_content():
    text = (
        "<!-- before -->"
        f'<sketch xmlns="{cpsk_core.NAMESPACE}" xmlns:fc="urn:freecad" version="0.1" fc:doc="d">'
        "<metadata><title>A &amp; B</title><fc:note>kept <b>as is</b></fc:note></metadata>"
        '<geometry><!-- the hole --><circle id="c" cx="0" cy="0" r="1" fc:active="false">'
        '<radius value="w &lt; 2 ? 1 : 2" fc:label="1"/><future/></circle><spline/></geometry>'
        "</sketch>"
    )
    first = document.parse(text).write()
    assert document.parse(first).write() == first
    for kept in [
        "<!-- before -->",
        "<!-- the hole -->",
        'xmlns:fc="urn:freecad"',
        'fc:doc="d"',
        "<title>A &amp; B</title>",
        'fc:active="false"',
        'value="w &lt; 2 ? 1 : 2"',
        'fc:label="1"',
        "<future/>",
        "<spline/>",
        "<fc:note>",
    ]:
        assert kept in first, kept


def test_descendants_walk_every_element_in_document_order():
    child = cpsk_core.element("point", id="a")
    extension = cpsk_core.Element("note", children=[child, cpsk_core.Comment("skipped")], namespace="urn:other")
    root = cpsk_core.Element("sketch", children=[extension, cpsk_core.element("point", id="b")])
    assert list(root.descendants()) == [extension, child, root.children[1]]


def test_documents_built_in_code_compile():
    built = cpsk_core.Document.new(unit_length="mm")
    geometry = built.container("geometry", create=True)
    variables = built.container("variables", create=True)
    assert [c.name for c in built.root.elements()] == ["variables", "geometry"]
    variables.append(cpsk_core.element("variable", id="r", type="length", value="2.5"))
    circle = geometry.append(cpsk_core.element("circle", id="c", cx=1, cy=0.1, r=2.5))
    circle.append(cpsk_core.element("radius", value="r"))
    geometry.append(cpsk_core.element("arc", cx=0, cy=0, r=1, start_angle=0, end_angle=90.5))
    text = built.write()
    assert '<arc cx="0" cy="0" r="1" start-angle="0" end-angle="90.5"/>' in text
    sketch = cpsk_core.loads(text)
    assert sketch.constraints[0].value == 2.5
    assert sketch.document is not None
    assert sketch.document.write() == text


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (40.0, "40"),
        (-3, "-3"),
        (0.1, "0.1"),
        (1 / 3, "0.3333333333333333"),
        (-0.0, "0"),
        (1e20, "1e+20"),
    ],
)
def test_numbers_are_written_to_round_trip(value, text):
    assert cpsk_core.format_number(value) == text
    assert float(text) == value


def test_infinite_numbers_cannot_be_written():
    with pytest.raises(ValueError, match="finite"):
        cpsk_core.format_number(float("inf"))


def test_constraints_are_nested_canonically():
    """Spec §11.4: under `about`'s owner (symmetric), else the first operand primitive."""
    text = f"""<sketch xmlns="{cpsk_core.NAMESPACE}" version="0.1">
      <geometry>
        <line id="a" x1="0" y1="0" x2="4" y2="0"/>
        <line id="b" x1="4" y1="0" x2="4" y2="3"/>
        <line id="c" x1="4" y1="3" x2="0" y2="0"/>
        <point id="p" x="1" y="1"/><point id="q" x="3" y="1"/>
      </geometry>
      <constraints>
        <coincident a="a.start" b="origin"/>
        <horizontal of="a"/>
        <!-- the joint -->
        <coincident a="b.start" b="a.end"/>
        <coincident a="c.end" b="a.start"/>
        <distance id="w" of="a" value="4"/>
        <symmetric a="p" b="q" about="b"/>
        <distance-x a="origin" b="p" value="1"/>
        <point-on point="q" object="c"/>
        <equal a="b" b="b"/>
      </constraints>
    </sketch>"""
    parsed = document.parse(text)
    cpsk_core.nest_constraints(parsed)
    written = parsed.write()
    assert "<constraints>" not in written
    assert (
        """\
    <line id="a" x1="0" y1="0" x2="4" y2="0">
      <coincident a="self.start" b="origin"/>
      <horizontal/>
      <!-- the joint -->
      <coincident a="b.start" b="self.end"/>
      <coincident a="c.end" b="self.start"/>
      <distance id="w" value="4"/>
    </line>

    <line id="b" x1="4" y1="0" x2="4" y2="3">
      <symmetric a="p" b="q"/>
      <equal b="self"/>
    </line>

    <line id="c" x1="4" y1="3" x2="0" y2="0">
      <point-on point="q"/>
    </line>

    <point id="p" x="1" y="1">
      <distance-x a="origin" value="1"/>
    </point>
"""
        in written
    )
    nested = cpsk_core.compile_document(parsed).constraints
    top = cpsk_core.loads(text).constraints
    assert sorted((c.type, c.value) for c in nested) == sorted((c.type, c.value) for c in top)


_PERPENDICULAR_GEOMETRY = """<geometry>
  <line id="l" x1="0" y1="0" x2="10" y2="0"/><line id="n" x1="10" y1="0" x2="10" y2="5"/>
  <arc id="k" cx="13" cy="0" r="3" start-angle="180" end-angle="270"/>
  <arc id="j" cx="0" cy="5" r="2" start-angle="0" end-angle="90"/>
  <circle id="c" cx="20" cy="0" r="2"/><point id="p" x="1" y="1"/>
</geometry>"""


@pytest.mark.parametrize(
    ("constraint", "ok"),
    [
        ('<perpendicular a="l" b="n"/>', True),
        ('<perpendicular a="l" b="k"/>', True),  # the line through the arc's centre
        ('<perpendicular a="c" b="l"/>', True),
        ('<perpendicular a="l.end" b="k.start"/>', True),  # end points of a line and an arc
        ('<perpendicular a="k.start" b="l.end"/>', True),
        ('<perpendicular a="l.end" b="n.start"/>', False),  # two lines' end points
        ('<perpendicular a="k.end" b="j.start"/>', False),  # two arcs' end points
        ('<perpendicular a="k" b="c"/>', False),  # two curves
        ('<perpendicular a="l.end" b="k.center"/>', False),
        ('<perpendicular a="l" b="p"/>', False),
    ],
)
def test_perpendicular_forms(constraint, ok):
    text = doc(f"{_PERPENDICULAR_GEOMETRY}<constraints>{constraint}</constraints>")
    if ok:
        assert cpsk_core.loads(text).constraints[0].type == "perpendicular"
    else:
        assert load_error(text) == {"operand"}


def test_perpendicular_nests_in_arcs_and_circles():
    body = """<geometry><line id="l" x1="0" y1="0" x2="10" y2="0"/>
      <arc cx="13" cy="0" r="3" start-angle="180" end-angle="270">
        <perpendicular a="self.start" b="l.end"/></arc>
      <circle cx="20" cy="0" r="2"><perpendicular b="l"/></circle></geometry>"""
    kinds = [tuple(op.kind for op in c.operands.values()) for c in cpsk_core.loads(doc(body)).constraints]
    assert [sorted(k) for k in kinds] == [["point", "point"], ["circle", "line"]]
