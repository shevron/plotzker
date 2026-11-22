"""The hex-profile nut slot: oriented right, and it holds a nut against turning."""

import pytest
from pythonscad import union

from cadder.hardware import hex_nut, metric
from cadder.printing import _ROTATIONS, Tolerances, nut_slot
from cadder.testing import bounding_box, volume

TOL = Tolerances()

AXES = "xyz"


@pytest.mark.parametrize(("axis", "entrance"), list(_ROTATIONS))
def test_orientation(axis, entrance):
    lo, hi = bounding_box(nut_slot(3, 10, axis, entrance))
    af = metric(3).nut_af + TOL.nut_slot
    a, e = AXES.index(axis), AXES.index(entrance[1])
    assert hi[a] - lo[a] == pytest.approx(TOL.nut_trap_h(3), abs=0.02)
    sign = 1 if entrance[0] == "+" else -1
    assert sign * (hi[e] if sign > 0 else lo[e]) == pytest.approx(10, abs=0.02)
    floor = lo[e] if sign > 0 else hi[e]
    assert abs(floor) == pytest.approx(af / 2, abs=0.02)


def test_nut_fits_flat_first_and_cannot_turn():
    slot = nut_slot(3, 10, "y", "+z")
    nut = hex_nut(3).rotate([90, 0, 0])  # bolt axis along y, corners along x
    nut_lo, nut_hi = bounding_box(nut)
    cy = (nut_lo[1] + nut_hi[1]) / 2
    nut = nut.translate([0, -cy, 0])
    assert volume(nut - slot) < 1e-3  # the nut fits
    # turned 10° it no longer does: the hex walls hold it
    turned = union(nut.rotate([0, 10, 0]))
    assert volume(turned - slot) > 0.05


def test_extra_thickness_widens_only_the_slot_thickness():
    lo, hi = bounding_box(nut_slot(3, 10, "x", "+z"))
    lo2, hi2 = bounding_box(nut_slot(3, 10, "x", "+z", extra_t=0.2))
    assert (hi2[0] - lo2[0]) - (hi[0] - lo[0]) == pytest.approx(0.2, abs=0.01)
    assert hi2[1] - lo2[1] == pytest.approx(hi[1] - lo[1], abs=0.01)
