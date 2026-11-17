"""Y gantry: 2 × gantry end bracket on 4 × SCS10UU, the 4020 beam, Y belt clamps,
the X motor / idler / endstop mounts and fasteners (fit check, T3.2 + T3.4).

Machine frame (``params``). Not printable.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, mirror, translate

from plotter_cad.geometry import frame_axes, get_handle, get_handles, shift_handle
from plotter_cad.hardware import (
    GT2,
    PULLEY,
    SCS10UU,
    endstop_keepout,
    endstop_placed,
    gt2_idler,
    gt2_pulley,
    hex_nut,
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
    LOOM,
    TOL,
    X_BELT,
    X_DRIVE,
    X_TENSIONER,
    Y_AXIS,
)
from plotter_cad.parts.belt_clamp import belt_clamp
from plotter_cad.parts.gantry_end_bracket import Side, gantry_end_bracket_local
from plotter_cad.parts.loom_anchor import loom_anchor_installed
from plotter_cad.parts.tension_idler import slider_x0
from plotter_cad.parts.x_idler_mount import x_idler_mount_installed
from plotter_cad.parts.x_idler_slider import x_idler_slider_installed
from plotter_cad.parts.x_motor_mount import x_motor_mount_left

if TYPE_CHECKING:
    from pythonscad import Solid


def x_endstop_keepout() -> Solid:
    """Space that must stay free for the X endstop's plug, in the left bracket-local frame."""
    return place_in_frame(
        endstop_keepout(), *frame_axes(get_handle(x_idler_mount_installed(), "board"))
    )


def x_drive_local(side: Side) -> list[Solid]:
    """X motor (right) or idler + endstop (left) at one gantry end, left-local frame."""
    if side is Side.RIGHT:
        mount = x_motor_mount_left()
        return [
            mount.color("DarkOrange"),
            nema17().align(get_handle(mount, "motor")),
            gt2_pulley().align(get_handle(mount, "pulley")),
            *[shcs(3, 10).align(h) for h in get_handles(mount, "motor_screws")],
        ]
    mount = x_idler_mount_installed()
    axle = get_handle(mount, "axle")
    t = X_TENSIONER
    slider_rear_x = frame_axes(get_handle(mount, "screw"))[0][0] + slider_x0(t)
    return [
        mount.color("DarkOrange"),
        x_idler_slider_installed().color("Orange"),
        gt2_idler().rotate([90, 0, 0]).translate([X_DRIVE.idler_x, X_BELT.y, t.axle_z]),
        shcs(t.axle_m, 25).align(axle),
        hex_nut(t.axle_m)
        .rotate([0, 0, 90])
        .rotate([-90, 0, 0])
        .translate([X_DRIVE.idler_x, X_BELT.y + t.nut_seat_y, t.axle_z]),
        shcs(t.screw_m, t.screw_len).align(get_handle(mount, "screw")),
        hex_nut(t.screw_m)
        .rotate([0, 0, 90])
        .rotate([0, 90, 0])
        .translate([slider_rear_x + TOL.nut_wall, X_BELT.y, t.screw_z]),
        endstop_placed(*frame_axes(get_handle(mount, "board"))),
    ]


def gantry_end_local(side: Side = Side.LEFT) -> list[Solid]:
    """One gantry end in the left bracket-local frame (the caller mirrors the right end).

    ``side`` selects the X drive hardware: LEFT = idler + endstop, RIGHT = motor.
    """
    bracket = gantry_end_bracket_local(side)
    items = [bracket.color("DarkOrange")]
    items += [
        scs10uu().translate([0, block * Y_AXIS.scs_pitch / 2, -SCS10UU.height]) for block in (-1, 1)
    ]
    # 8 × M5 into the blocks; the rear block's 4 also clamp the X motor/idler foot (M5×25)
    items += [shcs(5, 20).align(bolt) for bolt in get_handles(bracket, "block_bolts_front")]
    foot_top = X_DRIVE.foot_t
    recess = X_DRIVE.foot_head_recess if side is Side.RIGHT else 0  # motor mount: counterbored
    for bolt in get_handles(bracket, "block_bolts_rear"):
        # the idler mount's foot clamps the rear row; the motor mount's the front row
        rear_row = bolt[1][3] > Y_AXIS.scs_pitch / 2
        clamped = rear_row if side is Side.LEFT else not rear_row
        items.append(
            shcs(5, 25 if clamped else 20).align(
                shift_handle(bolt, [0, 0, foot_top - recess if clamped else 0])
            )
        )
    items += x_drive_local(side)
    items += [shcs(5, 20).align(bolt) for bolt in get_handles(bracket, "beam_bolts")]
    for mount in get_handles(bracket, "belt_clamps"):
        clamp = belt_clamp()
        items.append(clamp.align(mount, get_handle(clamp, "mount")).color("Gold"))
        items.append(
            cube([GT2.width, CLAMP.length, GT2.thickness])
            .translate([-GT2.width / 2, 0, -GT2.thickness])
            .align(mount)
            .color("#111")
        )
    items.append(shcs(3, BRACKET.trig_screw_len).align(get_handle(bracket, "trigger_screw")))
    if side is Side.RIGHT:
        items.append(loom_anchor_installed().color("DarkOrange"))
        items += [
            shcs(3, LOOM.anchor_screw_len).align(shift_handle(h, [0, 0, LOOM.anchor_h]))
            for h in get_handles(bracket, "loom_anchor")
        ]
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
                X_BELT.pulley_axis_z + PULLEY.pd / 2 - GT2.pitch_line_from_back,
            ]
        )
        .color("#111")
    )  # X belt upper (return) run, idler to pulley
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
