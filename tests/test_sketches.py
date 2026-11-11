"""SVG sketches load at 1 unit = 1 mm, with the origin at the bottom-left corner."""

import pytest

from plotter_cad.geometry import load_sketch
from plotter_cad.hardware import VSLOT
from plotter_cad.hardware.vslot import PROFILE_SKETCHES, SKETCH_DIR, vslot_profile


def outline_stats(sketch) -> tuple[float, list[float], list[float]]:
    """Net area (holes count negative) and bounding box of a 2D object."""
    outlines = sketch.mesh()
    area = sum(
        (a[0] * b[1] - b[0] * a[1]) / 2
        for outline in outlines
        for a, b in zip(outline, outline[1:] + outline[:1], strict=True)
    )
    points = [p for outline in outlines for p in outline]
    lo = [min(p[i] for p in points) for i in (0, 1)]
    hi = [max(p[i] for p in points) for i in (0, 1)]
    return area, lo, hi


# Net material areas of the profiles as drawn (slots, bores and the 2040's cavity removed).
@pytest.mark.parametrize(("size", "area"), [((1, 1), 161.1), ((1, 2), 295.5), ((2, 1), 295.5)])
def test_vslot_profile(size, area):
    got_area, lo, hi = outline_stats(vslot_profile(size))
    assert lo == pytest.approx([0, 0], abs=1e-6)
    assert hi == pytest.approx([size[0] * VSLOT.unit, size[1] * VSLOT.unit], abs=1e-6)
    assert got_area == pytest.approx(area, abs=0.5)


def test_every_registered_sketch_exists():
    for name, _ in PROFILE_SKETCHES.values():
        assert (SKETCH_DIR / name).is_file()


def test_unknown_profile_size():
    with pytest.raises(ValueError, match="No V-slot sketch"):
        vslot_profile((2, 2))


def test_missing_sketch(tmp_path):
    with pytest.raises(FileNotFoundError, match="Sketch not found"):
        load_sketch(tmp_path / "nope.svg")


def test_curve_facets_follow_fn():
    coarse = load_sketch(SKETCH_DIR / "vslot_2020.svg")
    fine = load_sketch(SKETCH_DIR / "vslot_2020.svg", fn=64)
    assert sum(map(len, fine.mesh())) > sum(map(len, coarse.mesh()))
