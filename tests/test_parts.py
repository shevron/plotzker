"""Every printable part is a sane, printable solid."""

import math

import pytest
from cadder.render import export_stls
from cadder.testing import bounding_box, shell_count, volume

from plotzker.parts import PARTS
from plotzker.project import PROJECT


def assert_printable(solid):
    """One piece with no enclosed voids, resting on the print bed, with real volume."""
    lo, hi = bounding_box(solid)
    assert shell_count(solid) == 1, "loose pieces or enclosed voids"
    assert lo[2] == pytest.approx(0, abs=1e-6), "print face must lie on z = 0"
    assert 0 < volume(solid) < math.prod(h - low for low, h in zip(lo, hi, strict=True))


@pytest.mark.parametrize("name", PARTS)
def test_part_is_printable(name):
    assert_printable(PARTS[name].build())


def test_stl_export_writes_every_part(tmp_path):
    written = export_stls(PROJECT, out_dir=tmp_path)
    assert sorted(path.name for path in written) == sorted(f"{n}.stl" for n in PARTS)
    assert all(path.stat().st_size > 0 for path in written)


def test_stl_export_rejects_unknown_names(tmp_path):
    with pytest.raises(SystemExit, match="Unknown name"):
        export_stls(PROJECT, ["no_such_part"], out_dir=tmp_path)


def test_x_carriage_clamp_nuts_each_have_a_pocket_and_a_roof():
    """T3.13: each belt clamp nut fits its own pocket (flat-first) and has plastic above it."""
    from cadder.hardware import hex_nut, metric
    from pythonscad import cube

    from plotzker.params import CLAMP, TOL, X_BELT
    from plotzker.parts.x_carriage import CLAMP_X, x_carriage_installed

    carriage = x_carriage_installed()
    nut_z = X_BELT.back_z - CLAMP.nut_z - TOL.nut_trap_height(3) / 2
    nut = hex_nut(3).translate([0, 0, -metric(3).nut_height / 2])  # corners along x
    for sx in (-1, 1):
        for sy in (-1, 1):
            # rear nut: flat toward the back (corners along x); front nut: flat toward the end
            placed = nut if sy > 0 else nut.rotate([0, 0, 90])
            at = [sx * CLAMP_X, X_BELT.y + sy * CLAMP.screw_dx, nut_z]
            assert volume(placed.translate(at) & carriage) < 1e-3, "nut collides"
            # just above the pocket, near its far corner (the front one is under the 45° ramp)
            roof = cube([1, 1, 1]).translate([at[0] - 3, at[1] - 3, X_BELT.back_z - 3.9])
            assert volume(roof & carriage) > 0.9, "no roof above the nut"


def test_one_slider_serves_all_three_idlers():
    """T3.26: the X idler and both Y idlers use the same unmirrored slider: the part's shape
    doesn't depend on where the idler is, and on both Y sides the axle bolt's head is on the
    arm the slider has for it (the right mount's tower is flipped instead)."""
    from plotzker.params import X_IDLER, Y_IDLER
    from plotzker.parts.floating_idler import slider_for_print
    from plotzker.parts.y_idler_mount import idler_for
    from plotzker.types import Side

    assert X_IDLER.head_side == Y_IDLER.head_side
    reference = slider_for_print(X_IDLER)
    other = slider_for_print(Y_IDLER)
    assert volume(other - reference) < 1e-3 and volume(reference - other) < 1e-3
    assert idler_for(Side.RIGHT).head_side == -idler_for(Side.LEFT).head_side
