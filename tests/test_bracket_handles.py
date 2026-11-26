"""The plotter's parts expose usable handles."""

import pytest
from cadder.handles import get_handle, get_handles
from cadder.testing import bounding_box

from plotzker.params import BRACKET, CLAMP
from plotzker.parts.belt_clamp import belt_clamp
from plotzker.parts.gantry_end_bracket import Side, gantry_end_bracket


@pytest.mark.parametrize("side", Side)
def test_bracket_block_bolts_sit_on_the_base_top(side):
    bracket = gantry_end_bracket(side)
    for name in ("block_bolts_front", "block_bolts_rear"):
        bolts = get_handles(bracket, name)
        assert len(bolts) == 4
        assert all(b[2][3] == BRACKET.base_thickness for b in bolts)


def test_right_bracket_handles_are_mirrored():
    left = get_handles(gantry_end_bracket(Side.LEFT), "beam_bolts")
    right = get_handles(gantry_end_bracket(Side.RIGHT), "beam_bolts")
    assert [r[0][3] for r in right] == pytest.approx([-x[0][3] for x in left])
    assert [r[2][3] for r in right] == pytest.approx([x[2][3] for x in left])


def test_belt_clamp_mounts_flush_under_the_bracket():
    """The clamp's ``mount`` handle on a bracket clamp handle hangs it below the underside."""
    clamp = belt_clamp()
    mount = get_handles(gantry_end_bracket(Side.LEFT), "belt_clamps")[0]
    low, high = bounding_box(clamp.align(mount, get_handle(clamp, "mount")))
    assert high[2] == pytest.approx(0, abs=1e-9)
    assert low[2] == pytest.approx(-CLAMP.total_thickness)
