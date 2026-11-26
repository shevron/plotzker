"""1:1 SVG drawings and Markdown tables."""

from cadder.drawing import SvgDrawing, markdown_table, stroke


def test_drawing_flips_y_and_sizes_the_sheet_in_mm() -> None:
    drawing = SvgDrawing(100, 50)
    drawing.rect(10, 5, 30, 15, stroke("#000", 0.4))
    drawing.circle(20, 40, 2.5, stroke("#c00", 0.5))
    svg = drawing.to_svg()
    assert 'width="100mm" height="50mm" viewBox="0 0 100 50"' in svg
    assert '<rect x="10" y="35" width="20" height="10" fill="none" stroke="#000"' in svg
    assert '<circle cx="20" cy="10" r="2.5"' in svg


def test_label_is_centered_text() -> None:
    drawing = SvgDrawing(10, 10)
    drawing.rect(0, 0, 10, 10, "", label="box")
    assert 'text-anchor="middle"' in drawing.elements[1] and ">box</text>" in drawing.elements[1]


def test_dashed_stroke_and_scale_bar() -> None:
    assert stroke("#06c", 0.4, "6 3").endswith('stroke-dasharray="6 3"')
    drawing = SvgDrawing(200, 100)
    drawing.scale_bar(20, 20, 100)
    assert drawing.elements == [
        '<path d="M20,80h100" stroke="#000" stroke-width="1"/>'
        '<path d="M20,76v8M120,76v8" stroke="#000" stroke-width="1"/>'
    ]


def test_markdown_table() -> None:
    table = markdown_table(("#", "Name", "x"), [(1, "hole", 2.5), (2, "slot", 10.0)])
    assert table.splitlines() == [
        "| # | Name | x |",
        "|---|------|---|",
        "| 1 | hole | 2.5 |",
        "| 2 | slot | 10 |",
    ]
