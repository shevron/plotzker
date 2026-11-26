"""Sketches load at 1 unit = 1 mm: SVG with the origin at the bottom-left corner, CPSK in its
own coordinates."""

import math
from pathlib import Path

import pytest

from cadder import cpsk
from cadder.geometry import load_sketch, teardrop
from cadder.hardware import VSLOT_SPEC
from cadder.hardware.vslot import PROFILE_SKETCHES, SKETCH_DIR, vslot_profile

CPSK_EXAMPLE = Path(__file__).parents[1] / "docs" / "cpsk" / "examples" / "plate-with-hole.cpsk"


def outline_stats(sketch) -> tuple[float, list[float], list[float]]:
    """Net area (holes count negative) and bounding box of a 2D object."""
    outlines = sketch.mesh()
    area = sum(
        (a[0] * b[1] - b[0] * a[1]) / 2
        for outline in outlines
        for a, b in zip(outline, outline[1:] + outline[:1], strict=True)
    )
    points = [p for outline in outlines for p in outline]
    low = [min(p[i] for p in points) for i in (0, 1)]
    high = [max(p[i] for p in points) for i in (0, 1)]
    return area, low, high


@pytest.mark.parametrize("size", PROFILE_SKETCHES)
def test_vslot_profile_fills_its_envelope(size):
    """Each profile spans exactly its ``n × m`` units from the origin and is not solid."""
    area, low, high = outline_stats(vslot_profile(size))
    width, height = size[0] * VSLOT_SPEC.unit, size[1] * VSLOT_SPEC.unit
    assert low == pytest.approx([0, 0], abs=1e-6)
    assert high == pytest.approx([width, height], abs=1e-6)
    assert 0 < area < width * height


def test_vslot_profile_lying_flat_is_the_upright_one_rotated():
    upright, _, _ = outline_stats(vslot_profile((1, 2)))
    flat, _, _ = outline_stats(vslot_profile((2, 1)))
    assert flat == pytest.approx(upright)


def test_unknown_profile_size():
    with pytest.raises(ValueError, match="No V-slot sketch"):
        vslot_profile((2, 2))


def test_missing_sketch(tmp_path):
    with pytest.raises(FileNotFoundError, match="Sketch not found"):
        load_sketch(tmp_path / "nope.svg")


def test_sketch_units_origin_and_holes(tmp_path):
    """A 30 × 20 mm plate with a 10 × 10 hole, drawn off-center in a 40 × 50 mm sheet."""
    svg = tmp_path / "plate.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="50mm" viewBox="0 0 40 50">'
        '<path fill-rule="evenodd" d="M5,25 H35 V45 H5 Z M10,30 H20 V40 H10 Z"/></svg>'
    )
    area, low, high = outline_stats(load_sketch(svg))
    assert area == pytest.approx(30 * 20 - 10 * 10)
    # SVG y runs down from the top of the sheet; CAD y runs up from its bottom
    assert low == pytest.approx([5, 5])
    assert high == pytest.approx([35, 25])


def test_curve_facets_follow_fn():
    coarse = load_sketch(SKETCH_DIR / "vslot_2020.svg")
    fine = load_sketch(SKETCH_DIR / "vslot_2020.svg", fn=64)
    assert sum(map(len, fine.mesh())) > sum(map(len, coarse.mesh()))


def test_teardrop_covers_the_hole_and_peaks_at_45_degrees():
    """As wide as the hole, with the roof's point where two 45° lines off the circle meet."""
    d = 6
    _, low, high = outline_stats(teardrop(d))
    assert low == pytest.approx([-d / 2, -d / 2], abs=1e-3)
    assert high == pytest.approx([d / 2, d / 2 * 2**0.5], abs=1e-3)


def cpsk_file(tmp_path, geometry: str) -> Path:
    """A CPSK sketch file with this ``<geometry>`` content."""
    path = tmp_path / "sketch.cpsk"
    path.write_text(f'<sketch xmlns="{cpsk.NAMESPACE}" version="0.1"><geometry>{geometry}</geometry></sketch>')
    return path


def test_cpsk_sketch_is_solved_with_params():
    """The example plate (40 × 25 with a hole of a third of the short side) at another size."""
    area, low, high = outline_stats(load_sketch(CPSK_EXAMPLE, fn=720, params={"width": "6cm"}))
    assert low == pytest.approx([0, 0], abs=1e-6)
    assert high == pytest.approx([60, 25], abs=1e-6)
    assert area == pytest.approx(60 * 25 - math.pi * (25 / 6) ** 2, rel=1e-4)


def test_cpsk_sketch_keeps_negative_coordinates(tmp_path):
    path = cpsk_file(tmp_path, '<circle cx="-3" cy="-4" r="2"><block/></circle>')
    _, low, high = outline_stats(load_sketch(path, fn=360))
    assert low == pytest.approx([-5, -6], abs=1e-6)
    assert high == pytest.approx([-1, -2], abs=1e-6)


def test_cpsk_warnings_and_strict(tmp_path):
    path = cpsk_file(tmp_path, '<circle cx="0" cy="0" r="2"/>')
    with pytest.warns(cpsk.CpskWarning, match="degrees of freedom"):
        load_sketch(path)
    with pytest.raises(cpsk.CpskSolveError):
        load_sketch(path, strict=True)


def test_cpsk_open_geometry_is_an_error(tmp_path):
    path = cpsk_file(tmp_path, '<line x1="0" y1="0" x2="5" y2="0"><block/></line>')
    with pytest.raises(cpsk.CpskExportError):
        load_sketch(path)


def test_params_need_a_cpsk_sketch():
    with pytest.raises(ValueError, match=r"only valid for \.cpsk"):
        load_sketch(SKETCH_DIR / "vslot_2020.svg", params={"width": 1})
