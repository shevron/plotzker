"""Assemblies build, and their parts actually meet: nothing floats in mid-air."""

import pytest
from pythonscad import union

from plotter_cad.assemblies import ASSEMBLIES
from plotter_cad.assemblies.carriage import carriage_fit_check
from plotter_cad.assemblies.gantry import (
    gantry_assembly,
    gantry_end_local,
    gantry_fit_check,
    x_endstop_keepout,
)
from plotter_cad.assemblies.skeleton import carriage_x_at, gantry_y_at
from plotter_cad.assemblies.y_drive import gantry_y_at as y_gantry_y_at
from plotter_cad.assemblies.y_drive import y_drive_assembly, y_drive_fit_check, y_endstop_keepout
from plotter_cad.hardware import sk10, y_shaft
from plotter_cad.params import FRAME, Y_AXIS
from plotter_cad.parts.gantry_end_bracket import Side
from plotter_cad.parts.y_idler_mount import y_idler_mount_installed
from plotter_cad.parts.y_motor_mount import y_motor_mount_installed
from solids import connected_groups, flatten, touching, volume


@pytest.mark.parametrize("name", ASSEMBLIES)
def test_assembly_builds(name):
    assert volume(union(*flatten(ASSEMBLIES[name]()))) > 0


# The skeleton is left out on purpose: its bed has nothing to sit on until the bed
# supports are designed (T3.7).
@pytest.mark.parametrize(
    "assembly",
    [
        carriage_fit_check,
        lambda: gantry_end_local(Side.LEFT),
        lambda: gantry_end_local(Side.RIGHT),
        gantry_fit_check,
        lambda: y_drive_fit_check(0),
        lambda: y_drive_fit_check(1),
    ],
    ids=[
        "carriage on the beam",
        "left gantry end",
        "right gantry end",
        "gantry on the shafts",
        "Y drive, gantry at the front",
        "Y drive, gantry at the back",
    ],
)
def test_assembly_is_connected(assembly):
    groups = connected_groups(assembly())
    assert len(groups) == 1, f"floating items (indices into the assembly list): {groups[1:]}"


def test_travel_stays_on_the_board():
    for position in (0, 1):
        assert 0 < gantry_y_at(position) < FRAME.board_size[1]
        assert 0 < carriage_x_at(position) < FRAME.board_size[0]


@pytest.mark.parametrize("position", [0, 0.5, 1])
def test_y_drive_clears_the_gantry(position):
    """Nothing of the Y drive collides with the gantry or the SK10s along the whole travel.

    The only contact allowed is the endstop lever being pressed by the trigger screw
    (under 3 mm³ per side at the front end, where the lever is drawn undeflected).
    """
    gantry_y = y_gantry_y_at(position)
    fixed = []
    for x in Y_AXIS.shaft_x:
        fixed.append(y_shaft().translate([x, Y_AXIS.shaft_y0, Y_AXIS.shaft_z]))
        fixed += [sk10().translate([x, y, 0]) for y in Y_AXIS.sk10_y]
    others = union(*flatten(gantry_assembly(gantry_y)), *fixed)
    drive = union(*flatten(y_drive_assembly(gantry_y)))
    assert volume(drive & others) < 2 * 3


@pytest.mark.parametrize("position", [0, 1])
def test_y_endstop_plug_space_is_free(position):
    """A plug can be pushed onto each Y endstop's connector: nothing is in the way."""
    gantry_y = y_gantry_y_at(position)
    solids = [*flatten(y_drive_assembly(gantry_y)), *flatten(gantry_assembly(gantry_y))]
    for side in Side:
        keepout = y_endstop_keepout(side)
        assert all(volume(keepout & s) < 0.1 for s in solids)


def test_x_endstop_plug_space_is_free():
    """A plug can be pushed onto the X endstop's connector: nothing is in the way."""
    keepout = x_endstop_keepout()
    assert all(volume(keepout & s) < 0.1 for s in flatten(gantry_end_local(Side.LEFT)))


@pytest.mark.parametrize(
    ("mount", "sk10_y"),
    [
        (y_idler_mount_installed, Y_AXIS.sk10_y[0]),
        (y_motor_mount_installed, Y_AXIS.sk10_y[1]),
    ],
    ids=["idler mount, front SK10", "motor mount, rear SK10"],
)
def test_sk10_seats_in_the_mount_pocket(mount, sk10_y):
    """The SK10 fits in its mount's pocket without overlap and rests against the end wall."""
    support = sk10().translate([0, sk10_y, 0])
    assert volume(mount() & support) < 1e-6
    assert touching(mount(), support)
