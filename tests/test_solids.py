"""The measuring helpers the other tests rely on."""

import pytest
from pythonscad import cube, sphere

from solids import bounding_box, connected_groups, shell_count, touching, volume


def test_volume_and_bounding_box():
    block = cube([10, 20, 30]).translate([1, 2, 3])
    assert volume(block) == pytest.approx(6000)
    lo, hi = bounding_box(block)
    assert lo == pytest.approx([1, 2, 3])
    assert hi == pytest.approx([11, 22, 33])


def test_volume_of_a_part_with_a_hole():
    assert volume(cube(10) - cube([4, 4, 20]).translate([3, 3, -5])) == pytest.approx(840)


def test_shell_count_finds_loose_pieces_and_voids():
    assert shell_count(cube(10)) == 1
    assert shell_count(cube(10) | cube(10).translate([20, 0, 0])) == 2
    assert shell_count(cube(10) - sphere(r=2, fn=16).translate([5, 5, 5])) == 2


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(5, True), (10, True), (10.5, False)],
    ids=["overlapping", "face to face", "apart"],
)
def test_touching(offset, expected):
    assert touching(cube(10), cube(10).translate([offset, 0, 0])) is expected


def test_connected_groups_links_solids_through_a_third():
    a, b, c = cube(10), cube(10).translate([10, 0, 0]), cube(10).translate([20, 0, 0])
    floating = cube(10).translate([0, 0, 50])
    assert connected_groups([a, [c, floating], b]) == [[0, 1, 3], [2]]
