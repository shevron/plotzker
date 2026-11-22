"""Handles: the helpers agree with plain transforms."""

import pytest
from pythonscad import cylinder

from cadder.handles import frame_axes, frame_handle, handle, shift_handle
from cadder.testing import bounding_box


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


def test_frame_handle_roundtrips_a_left_handed_frame():
    """A chiral part's frame (here left-handed) survives frame_handle → frame_axes unchanged."""
    origin, u, v, w = [1, 2, 3], [0, 0, -1], [0, 1, 0], [-1, 0, 0]
    assert frame_axes(frame_handle(origin, u, v, w)) == (origin, u, v, w)
