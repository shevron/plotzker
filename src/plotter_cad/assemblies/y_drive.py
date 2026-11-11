"""Y drive: motor and idler mounts, endstop mounts, motors, pulleys, idlers, endstop
boards, fasteners and belts (fit check, T3.5).

Machine frame (``params``). Not printable.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, mirror, translate

from plotter_cad.assemblies.gantry import gantry_assembly
from plotter_cad.hardware import (
    GT2,
    IDLER,
    NEMA17,
    PULLEY,
    endstop_placed,
    gt2_idler,
    gt2_pulley,
    hex_nut,
    nema17,
    shcs,
    sk10,
    washer,
    y_shaft,
)
from plotter_cad.params import BRACKET, FRAME, Y_AXIS, Y_DRIVE, Y_ENDSTOP
from plotter_cad.parts.gantry_end_bracket import Side
from plotter_cad.parts.y_idler_mount import y_idler_mount_installed
from plotter_cad.parts.y_motor_mount import y_motor_mount_installed

if TYPE_CHECKING:
    from pythonscad import Solid

_AXLE_LEN = 30  #: M5 idler axle


def y_idler_end_local(side: Side = Side.LEFT) -> list[Solid]:
    """Idler end of the left side: idler mount, idler, axle, tension screw, endstop."""
    d, belt_x, axis_z = Y_DRIVE, Y_AXIS.belt_x, Y_AXIS.pulley_axis_z
    x_out = d.idler_plate_x[0]  #: outboard face of the plate
    y_rear = d.idler_plate_y[1]
    plate_cx = sum(d.idler_plate_x) / 2
    inboard = belt_x + IDLER.width / 2 + 1  #: idler flange + one washer
    return [
        y_idler_mount_installed(side).color("DarkOrange"),
        gt2_idler().rotate([0, 90, 0]).translate([belt_x, d.idler_y, axis_z]),
        washer(5).rotate([0, 90, 0]).translate([belt_x + IDLER.width / 2, d.idler_y, axis_z]),
        washer(5).rotate([0, 90, 0]).translate([belt_x - IDLER.width / 2 - 1, d.idler_y, axis_z]),
        shcs(5, _AXLE_LEN).rotate([0, 90, 0]).translate([inboard, d.idler_y, axis_z]),
        washer(5).rotate([0, 90, 0]).translate([x_out - 1, d.idler_y, axis_z]),
        hex_nut(5).rotate([0, -90, 0]).translate([x_out - 1, d.idler_y, axis_z]),
        shcs(3, 20).rotate([-90, 0, 0]).translate([plate_cx, y_rear, axis_z]),
    ]


def y_motor_end_local() -> list[Solid]:
    """Motor end of the left side: motor mount, motor, pulley, motor screws."""
    d, axis_z = Y_DRIVE, Y_AXIS.pulley_axis_z
    x_face = d.motor_plate_x[1]
    pulley_x = d.pulley_hub_x
    screws = [
        shcs(3, 10)
        .rotate([0, -90, 0])
        .translate(
            [
                d.motor_plate_x[0],
                d.motor_y + dy * NEMA17.hole_pitch / 2,
                axis_z + dz * NEMA17.hole_pitch / 2,
            ]
        )
        for dy in (-1, 1)
        for dz in (-1, 1)
    ]
    return [
        y_motor_mount_installed().color("DarkOrange"),
        nema17().rotate([0, -90, 0]).translate([x_face, d.motor_y, axis_z]),
        gt2_pulley().rotate([0, -90, 0]).translate([pulley_x, d.motor_y, axis_z]),
        *screws,
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


def y_endstop_board(side: Side, gantry_y: float | None = None) -> Solid:
    """The endstop board of one side in the machine frame (its chirality can't be mirrored).

    With ``gantry_y`` the lever is drawn pressed if the trigger screw reaches it.
    """
    left_x, right_x = Y_AXIS.shaft_x
    e = Y_ENDSTOP
    if side is Side.LEFT:
        u_z, shaft_x, sign = -1, left_x, 1
    else:
        u_z, shaft_x, sign = 1, right_x, -1
    origin = [shaft_x + sign * e.board_x0, e.board_front_y, e.board_z_center(u_z)]
    # board axes in the machine frame: u along z, v = +y, w = toward the machine center
    pressed = gantry_y is not None and gantry_y <= gantry_y_at(0) + 1e-6
    return endstop_placed(origin, [0, 0, u_z * sign], [0, 1, 0], [sign, 0, 0], pressed)


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
