"""Every printable part is a sane, printable solid."""

import math

import pytest

from plotzker import build
from plotzker.parts import PRINTABLE_PARTS
from solids import bounding_box, shell_count, touching, volume


def assert_printable(solid):
    """One piece with no enclosed voids, resting on the print bed, with real volume."""
    lo, hi = bounding_box(solid)
    assert shell_count(solid) == 1, "loose pieces or enclosed voids"
    assert lo[2] == pytest.approx(0, abs=1e-6), "print face must lie on z = 0"
    assert 0 < volume(solid) < math.prod(h - low for low, h in zip(lo, hi, strict=True))


@pytest.mark.parametrize("name", PRINTABLE_PARTS)
def test_part_is_printable(name):
    assert_printable(PRINTABLE_PARTS[name]())


def test_stl_export_writes_every_part(tmp_path):
    written = build.export_stls(out_dir=tmp_path)
    assert sorted(path.name for path in written) == sorted(f"{n}.stl" for n in PRINTABLE_PARTS)
    assert all(path.stat().st_size > 0 for path in written)


def test_stl_export_rejects_unknown_names(tmp_path):
    with pytest.raises(SystemExit, match="Unknown name"):
        build.export_stls(["no_such_part"], out_dir=tmp_path)


def test_x_carriage_clamp_nuts_each_have_a_pocket_and_a_roof():
    """T3.13: each belt clamp nut fits its own pocket (flat-first) and has plastic above it."""
    from pythonscad import cube

    from plotzker.hardware import hex_nut, metric
    from plotzker.params import CLAMP, TOL, X_BELT
    from plotzker.parts.x_carriage import CLAMP_X, x_carriage_installed

    carriage = x_carriage_installed()
    nut_z = X_BELT.back_z - CLAMP.nut_z - TOL.nut_trap_h(3) / 2
    nut = hex_nut(3).translate([0, 0, -metric(3).nut_h / 2])  # corners along x
    for sx in (-1, 1):
        for sy in (-1, 1):
            # rear nut: flat toward the back (corners along x); front nut: flat toward the end
            placed = nut if sy > 0 else nut.rotate([0, 0, 90])
            at = [sx * CLAMP_X, X_BELT.y + sy * CLAMP.screw_dx, nut_z]
            assert volume(placed.translate(at) & carriage) < 1e-3, "nut collides"
            # just above the pocket, near its far corner (the front one is under the 45° ramp)
            roof = cube([1, 1, 1]).translate([at[0] - 3, at[1] - 3, X_BELT.back_z - 3.9])
            assert volume(roof & carriage) > 0.9, "no roof above the nut"


def test_tension_idler_slider_is_free_of_the_rail():
    """The slider rides on the rail's dovetail without touching it (a sliding fit)."""
    from plotzker.parts.tension_idler import rail, slider

    assert not touching(rail(), slider())
