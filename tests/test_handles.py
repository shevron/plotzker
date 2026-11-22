"""Handles: the helpers agree with plain transforms, and parts expose usable handles."""

import pytest
from cadder.handles import frame_axes, frame_handle, get_handle, get_handles, handle, shift_handle
from cadder.testing import bounding_box
from pythonscad import cylinder

from plotzker.params import BRACKET, CLAMP
from plotzker.parts.belt_clamp import belt_clamp
from plotzker.parts.gantry_end_bracket import Side, gantry_end_bracket


@pytest.mark.parametrize("rotation", [(0, 0, 0), (90, 0, 0), (-90, 0, 0), (0, -90, 0), (0, 0, 90)])
def test_align_to_handle_matches_rotate_and_translate(rotation):
    """``align(handle(p, r))`` places a part exactly like ``rotate(r).translate(p)``."""
    part = cylinder(d=2, h=5, fn=16).translate([0.5, 0, 0])
    expected = bounding_box(part.rotate(list(rotation)).translate([1, 2, 3]))
    actual = bounding_box(part.align(handle([1, 2, 3], rotation)))
    assert [*actual[0], *actual[1]] == pytest.approx([*expected[0], *expected[1]], abs=1e-9)


def test_shift_handle_moves_in_the_outer_frame():
    moved = shift_handle(handle([1, 2, 3], [0, -90, 0]), [0, 0, 10])
    assert [row[3] for row in moved[:3]] == [1, 2, 13]


@pytest.mark.parametrize("side", Side)
def test_bracket_block_bolts_sit_on_the_base_top(side):
    bracket = gantry_end_bracket(side)
    for name in ("block_bolts_front", "block_bolts_rear"):
        bolts = get_handles(bracket, name)
        assert len(bolts) == 4
        assert all(b[2][3] == BRACKET.base_t for b in bolts)


def test_right_bracket_handles_are_mirrored():
    left = get_handles(gantry_end_bracket(Side.LEFT), "beam_bolts")
    right = get_handles(gantry_end_bracket(Side.RIGHT), "beam_bolts")
    assert [r[0][3] for r in right] == pytest.approx([-x[0][3] for x in left])
    assert [r[2][3] for r in right] == pytest.approx([x[2][3] for x in left])


def test_belt_clamp_mounts_flush_under_the_bracket():
    """The clamp's ``mount`` handle on a bracket clamp handle hangs it below the underside."""
    clamp = belt_clamp()
    mount = get_handles(gantry_end_bracket(Side.LEFT), "belt_clamps")[0]
    lo, hi = bounding_box(clamp.align(mount, get_handle(clamp, "mount")))
    assert hi[2] == pytest.approx(0, abs=1e-9)
    assert lo[2] == pytest.approx(-CLAMP.total_t)


def test_frame_handle_roundtrips_a_left_handed_frame():
    """A chiral part's frame (here left-handed) survives frame_handle → frame_axes unchanged."""
    origin, u, v, w = [1, 2, 3], [0, 0, -1], [0, 1, 0], [-1, 0, 0]
    assert frame_axes(frame_handle(origin, u, v, w)) == (origin, u, v, w)
