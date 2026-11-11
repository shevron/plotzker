"""Assemblies build, and their parts actually meet: nothing floats in mid-air."""

import pytest
from pythonscad import union

from plotter_cad.assemblies import ASSEMBLIES
from plotter_cad.assemblies.carriage import carriage_fit_check
from plotter_cad.assemblies.gantry import gantry_end_local, gantry_fit_check
from plotter_cad.assemblies.skeleton import carriage_x_at, gantry_y_at
from plotter_cad.params import FRAME
from plotter_cad.parts.gantry_end_bracket import Side
from solids import connected_groups, flatten, volume


@pytest.mark.parametrize("name", ASSEMBLIES)
def test_assembly_builds(name):
    assert volume(union(*flatten(ASSEMBLIES[name]()))) > 0


# The skeleton is left out on purpose: its bed and Y belt runs have nothing to sit on
# until the bed supports and Y drive are designed (T3.5, T3.7).
@pytest.mark.parametrize(
    "assembly",
    [
        carriage_fit_check,
        lambda: gantry_end_local(Side.LEFT),
        lambda: gantry_end_local(Side.RIGHT),
        gantry_fit_check,
    ],
    ids=["carriage on the beam", "left gantry end", "right gantry end", "gantry on the shafts"],
)
def test_assembly_is_connected(assembly):
    groups = connected_groups(assembly())
    assert len(groups) == 1, f"floating items (indices into the assembly list): {groups[1:]}"


def test_travel_stays_on_the_board():
    for position in (0, 1):
        assert 0 < gantry_y_at(position) < FRAME.board_size[1]
        assert 0 < carriage_x_at(position) < FRAME.board_size[0]
