"""Every printable part is a sane, printable solid."""

import math

import pytest

from plotter_cad import build
from plotter_cad.parts import PRINTABLE_PARTS
from solids import bounding_box, shell_count, volume


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
