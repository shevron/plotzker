"""Y drive: motor and idler mounts, endstop mounts, motors, pulleys, idlers, endstop
boards, fasteners and belts (fit check, T3.5).

Machine frame (``params``). Not printable.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, mirror, translate

from plotter_cad.assemblies.gantry import gantry_assembly
from plotter_cad.geometry import Matrix, frame_axes, get_handle, get_handles, shift_handle
from plotter_cad.hardware import (
    GT2,
    PULLEY,
    endstop_keepout,
    endstop_placed,
    gt2_idler,
    gt2_pulley,
    hex_nut,
    metric,
    nema17,
    place_in_frame,
    shcs,
    sk10,
    y_shaft,
)
from plotter_cad.params import BRACKET, FRAME, TOL, Y_AXIS, Y_DRIVE, Y_TENSIONER
from plotter_cad.parts.gantry_end_bracket import Side
from plotter_cad.parts.y_idler_mount import y_idler_mount_installed
from plotter_cad.parts.y_idler_slider import y_idler_slider_installed
from plotter_cad.parts.y_motor_mount import y_motor_mount_installed

if TYPE_CHECKING:
    from pythonscad import Solid

_AXLE_LEN = 25  #: M5 idler axle


def _at_x(mat: Matrix, x: float) -> Matrix:
    """``mat`` moved along x to ``x`` (the hardware stack along an axle)."""
    return shift_handle(mat, [x - mat[0][3], 0, 0])


def y_idler_end_local(side: Side = Side.LEFT) -> list[Solid]:
    """Idler end of the left side: idler mount, slider, idler, axle, tension screw."""
    mount = y_idler_mount_installed(side)
    axle = get_handle(mount, "axle")
    t = Y_TENSIONER
    slider_rear_y = Y_DRIVE.idler_y - t.axle_x
    return [
        mount.color("DarkOrange"),
        y_idler_slider_installed().color("Orange"),
        gt2_idler().align(_at_x(axle, Y_AXIS.belt_x)),
        shcs(t.axle_m, _AXLE_LEN).align(axle),
        hex_nut(t.axle_m)
        .rotate([0, -90, 0])
        .translate(
            [Y_AXIS.belt_x - t.width / 2 + metric(t.axle_m).nut_h, Y_DRIVE.idler_y, t.axle_z]
        ),
        shcs(t.screw_m, t.screw_len).align(get_handle(mount, "tension_screw")),
        hex_nut(t.screw_m)
        .rotate([-90, 0, 0])
        .translate([Y_AXIS.belt_x, slider_rear_y + TOL.nut_wall, t.screw_z]),
    ]


def y_motor_end_local() -> list[Solid]:
    """Motor end of the left side: motor mount, motor, pulley, motor screws."""
    mount = y_motor_mount_installed()
    return [
        mount.color("DarkOrange"),
        nema17().align(get_handle(mount, "motor")),
        gt2_pulley().align(get_handle(mount, "pulley")),
        *(shcs(3, 10).align(screw) for screw in get_handles(mount, "motor_screws")),
    ]


def y_belt_runs(gantry_y: float) -> list[Solid]:
    """Both runs of one side's belt, in the left side frame, for the gantry at ``gantry_y``.

    The top run is cut under the gantry: it runs from each pulley to the outer end of
    that end's belt clamp (the gantry model draws the belt inside the clamps).
    """
    d = Y_DRIVE
    x0 = Y_AXIS.belt_x - GT2.width / 2
    front_clamp_start = gantry_y - BRACKET.len_y / 2
    rear_clamp_end = gantry_y + BRACKET.len_y / 2
    lower_z = Y_AXIS.pulley_axis_z - PULLEY.pd / 2 - GT2.pitch_line_from_back
    upper_z = Y_AXIS.belt_back_z - GT2.thickness
    runs = [(d.idler_y, d.motor_y, lower_z)]
    runs += [(d.idler_y, front_clamp_start, upper_z), (rear_clamp_end, d.motor_y, upper_z)]
    return [
        cube([GT2.width, y1 - y0, GT2.thickness]).translate([x0, y0, z]).color("#111")
        for y0, y1, z in runs
    ]


def _y_endstop_frame(side: Side) -> tuple[list[float], list[float], list[float], list[float]]:
    """Endstop board frame in the machine frame (origin, then u, v, w), from the mount's
    handle in the left side frame. The right side is mirrored in x, but the chiral board is not
    mirrored with it: its u axis flips instead."""
    left_x, right_x = Y_AXIS.shaft_x
    origin, u, v, w = frame_axes(get_handle(y_idler_mount_installed(side), "board"))
    if side is Side.LEFT:
        return [left_x + origin[0], *origin[1:]], u, v, w
    return [right_x - origin[0], *origin[1:]], [-c for c in u], v, [-w[0], w[1], w[2]]


def y_endstop_board(side: Side, gantry_y: float | None = None) -> Solid:
    """The endstop board of one side in the machine frame.

    With ``gantry_y`` the lever is drawn pressed if the gantry is at its front end.
    """
    pressed = gantry_y is not None and gantry_y <= gantry_y_at(0) + 1e-6
    return endstop_placed(*_y_endstop_frame(side), pressed)


def y_endstop_keepout(side: Side) -> Solid:
    """Space that must stay free for the Y endstop's plug, in the machine frame."""
    return place_in_frame(endstop_keepout(), *_y_endstop_frame(side))


def y_drive_side_local(gantry_y: float, side: Side = Side.LEFT) -> list[Solid]:
    """One side's Y drive without the endstop board, in the left side frame (x from the shaft)."""
    return [*y_idler_end_local(side), *y_motor_end_local(), *y_belt_runs(gantry_y)]


def y_drive_assembly(gantry_y: float) -> list[Solid]:
    """Both sides' Y drives for the gantry at ``gantry_y``, in the machine frame."""
    left_x, right_x = Y_AXIS.shaft_x
    left = y_drive_side_local(gantry_y, Side.LEFT)
    right = y_drive_side_local(gantry_y, Side.RIGHT)
    return [
        translate(left, [left_x, 0, 0]),
        translate(mirror(right, [1, 0, 0]), [right_x, 0, 0]),
        y_endstop_board(Side.LEFT, gantry_y),
        y_endstop_board(Side.RIGHT, gantry_y),
    ]


def gantry_y_at(position: float) -> float:
    """Gantry center along Y; ``position`` 0 = front end of travel, 1 = back end."""
    return Y_DRIVE.gantry_front_y + BRACKET.len_y / 2 + position * Y_AXIS.travel_avail


def y_drive_fit_check(position: float = 0.0) -> list[Solid]:
    """Baseboard, shafts, SK10s, gantry and both Y drives, gantry at ``position`` (0..1)."""
    gantry_y = gantry_y_at(position)
    board_t = FRAME.board_size[2]
    items = [cube(list(FRAME.board_size)).translate([0, 0, -board_t]).color("BurlyWood", 0.5)]
    for x in Y_AXIS.shaft_x:
        items.append(y_shaft().translate([x, Y_AXIS.shaft_y0, Y_AXIS.shaft_z]))
        items += [sk10().translate([x, y, 0]) for y in Y_AXIS.sk10_y]
    return [*items, *gantry_assembly(gantry_y), *y_drive_assembly(gantry_y)]
