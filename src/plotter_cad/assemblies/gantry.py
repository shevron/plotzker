"""Y gantry: 2 × gantry end bracket on 4 × SCS10UU, the 4020 beam, Y belt clamps,
the X motor / idler / endstop mounts and fasteners (fit check, T3.2 + T3.4).

Machine frame (``params``). Not printable.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, mirror, translate

from plotter_cad.hardware import (
    GT2,
    IDLER,
    PULLEY,
    SCS10UU,
    VSLOT,
    endstop_keepout,
    endstop_placed,
    gt2_idler,
    gt2_pulley,
    nema17,
    place_in_frame,
    scs10uu,
    shcs,
    vslot_x,
    y_shaft,
)
from plotter_cad.params import (
    BEAM,
    BRACKET,
    CLAMP,
    FRAME,
    X_BELT,
    X_DRIVE,
    X_ENDSTOP,
    Y_AXIS,
)
from plotter_cad.parts.belt_clamp import belt_clamp
from plotter_cad.parts.gantry_end_bracket import BEAM_BOTTOM, FACE_OUT_X, Side, gantry_end_bracket
from plotter_cad.parts.x_endstop_mount import x_endstop_mount_installed
from plotter_cad.parts.x_idler_mount import x_idler_mount_installed
from plotter_cad.parts.x_idler_spacer import x_idler_spacer
from plotter_cad.parts.x_motor_mount import x_motor_mount_left

if TYPE_CHECKING:
    from pythonscad import Solid


#: X endstop board frame in the left bracket-local frame: origin, then u, v, w (board axes).
_X_ENDSTOP_FRAME = (
    [
        X_ENDSTOP.board_front_x,
        sum(X_ENDSTOP.board_y) / 2,
        X_ENDSTOP.board_bottom_z - Y_AXIS.scs_top_z,
    ],
    [0, -1, 0],
    [1, 0, 0],
    [0, 0, 1],
)


def x_endstop_keepout() -> Solid:
    """Space that must stay free for the X endstop's plug, in the left bracket-local frame."""
    return place_in_frame(endstop_keepout(), *_X_ENDSTOP_FRAME)


def x_drive_local(side: Side) -> list[Solid]:
    """X motor (right) or idler + endstop (left) at one gantry end, left-local frame."""
    axis_z = X_BELT.pulley_axis_z - Y_AXIS.scs_top_z
    d = X_DRIVE
    if side is Side.RIGHT:
        return [
            x_motor_mount_left().color("DarkOrange"),
            nema17().rotate([90, 0, 0]).translate([d.motor_x, d.motor_face_y, axis_z]),
            gt2_pulley().rotate([90, 0, 0]).translate([d.motor_x, d.pulley_hub_y, axis_z]),
        ]
    return [
        x_idler_mount_installed().color("DarkOrange"),
        x_endstop_mount_installed().color("Orange"),
        gt2_idler().rotate([90, 0, 0]).translate([d.idler_x, X_BELT.y, axis_z]),
        x_idler_spacer()
        .rotate([90, 0, 0])
        .translate([d.idler_x, d.plate_y0, axis_z])
        .color("Orange"),
        shcs(5, 40).rotate([90, 0, 0]).translate([d.idler_x, X_BELT.y - IDLER.width / 2, axis_z]),
        endstop_placed(*_X_ENDSTOP_FRAME),
    ]


def gantry_end_local(side: Side = Side.LEFT) -> list[Solid]:
    """One gantry end in the left bracket-local frame (the caller mirrors the right end).

    ``side`` selects the X drive hardware: LEFT = idler + endstop, RIGHT = motor.
    """
    items = [gantry_end_bracket(Side.LEFT).color("DarkOrange")]
    items += [
        scs10uu().translate([0, block * Y_AXIS.scs_pitch / 2, -SCS10UU.height]) for block in (-1, 1)
    ]
    # 8 × M5 into the blocks; the rear block's 4 also clamp the X motor/idler foot (M5×25)
    for block in (-1, 1):
        rear = block > 0
        for hx in (-1, 1):
            for hy in (-1, 1):
                items.append(
                    shcs(5, 25 if rear else 20).translate(
                        [
                            hx * SCS10UU.hole_pitch_x / 2,
                            block * Y_AXIS.scs_pitch / 2 + hy * SCS10UU.hole_pitch_y / 2,
                            BRACKET.base_t + (X_DRIVE.foot_t if rear else 0),
                        ]
                    )
                )
    items += x_drive_local(side)
    for z in (BEAM_BOTTOM + VSLOT.unit / 2, BEAM_BOTTOM + 3 * VSLOT.unit / 2):
        items.append(shcs(5, 20).rotate([0, -90, 0]).translate([FACE_OUT_X, 0, z]))
    for cy in (-BRACKET.len_y / 2, BRACKET.len_y / 2 - CLAMP.length):
        items.append(belt_clamp().translate([Y_AXIS.belt_x, cy, -CLAMP.total_t]).color("Gold"))
        items.append(
            cube([GT2.width, CLAMP.length, GT2.thickness])
            .translate([Y_AXIS.belt_x - GT2.width / 2, cy, -GT2.thickness])
            .color("#111")
        )
    # endstop trigger screw: head behind the boss, tip forward
    items.append(
        shcs(3, BRACKET.trig_screw_len)
        .rotate([-90, 0, 0])
        .translate([BRACKET.trig_x, -BRACKET.len_y / 2 + BRACKET.trig_boss[1], BRACKET.trig_z])
    )
    return items


def gantry_assembly(gantry_y: float) -> list[Solid]:
    """The whole gantry with its center (midway between the blocks) at machine y = ``gantry_y``."""
    left_x, right_x = Y_AXIS.shaft_x
    belt_return = (
        cube([Y_AXIS.shaft_spacing - X_DRIVE.idler_x - X_DRIVE.motor_x, GT2.width, GT2.thickness])
        .translate(
            [
                left_x + X_DRIVE.idler_x,
                gantry_y + X_BELT.y - GT2.width / 2,
                X_BELT.pulley_axis_z - PULLEY.pd / 2 - GT2.thickness + GT2.pitch_line_from_back,
            ]
        )
        .color("#111")
    )  # X belt lower (return) run, idler to pulley
    return [
        translate(gantry_end_local(Side.LEFT), [left_x, gantry_y, Y_AXIS.scs_top_z]),
        translate(
            mirror(gantry_end_local(Side.RIGHT), [1, 0, 0]), [right_x, gantry_y, Y_AXIS.scs_top_z]
        ),
        belt_return,
        vslot_x(BEAM.length, BEAM.size).translate(
            [left_x + BEAM.end_offset, gantry_y - BEAM.depth / 2, BEAM.bottom_z]
        ),
    ]


def gantry_fit_check() -> list[Solid]:
    """The gantry at mid-board on 400 mm stubs of the Y shafts."""
    mid_y = FRAME.board_size[1] / 2
    shafts = [y_shaft(400).translate([x, mid_y - 200, Y_AXIS.shaft_z]) for x in Y_AXIS.shaft_x]
    return [*gantry_assembly(mid_y), *shafts]
