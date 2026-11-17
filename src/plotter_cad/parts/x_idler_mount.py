"""X idler mount with the belt tensioner's rail (STATUS.md T3.4, T3.16). Print ×1 (left end).

Purpose: carries the X belt idler behind the beam at the left end of the gantry. The idler
turns on an M5 axle held at both ends by the U-shaped :mod:`x_idler_slider`, which rides on a
dovetail ridge on this foot (the rail); an M3 screw through the end block pulls the slider
outboard to tension the belt. The generic design is :mod:`tension_idler`; this mount is one
part with the rail built into the foot (no extra screws). The foot, inboard of the rail,
carries the X endstop board and sits on the left gantry bracket's base over the rear SCS
block, clamped by that block's rear 4 × M5 (they become M5×25). Its outboard end sticks out
past the bracket, carrying the end block.

  top view (belt behind the beam, at the bottom)

   M3 ─▓│ slider ═╗ ← idler (axle ⟂ page)        ┌──────────┐
      end│ ridge ═╝                              │ endstop  │
      block  ─── foot ────────────────────────────┴ board ───┘

Frame: LEFT bracket-local (``params.XDrive``), z = 0 on the SCS top face
(:func:`x_idler_mount_installed`); :func:`x_idler_mount` puts the foot on the bed.

Hardware: see :mod:`x_idler_slider` (idler, M5×25 axle + nut, M3 nut) + 1 × M3×25 ISO 4762
(tension screw, from the end block's outboard face); 2 × M3 nuts (pressed into the foot's
underside) + 2 × M3×6 (endstop board); 4 × M5×25 ISO 4762 replacing the rear SCS bolts of the
left bracket (rear row only; the front row's heads sit flush with the foot).
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports (the ridge's
45° flanks self-support).
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, union

from plotter_cad.geometry import (
    EPS,
    FN_HOLE,
    Matrix,
    frame_handle,
    handle,
    set_handles,
)
from plotter_cad.hardware import ENDSTOP, SCS10UU, metric
from plotter_cad.params import BRACKET, TOL, X_BELT, X_DRIVE, X_ENDSTOP, X_TENSIONER, Y_AXIS
from plotter_cad.parts.tension_idler import end_block, ridge, slider_x0

if TYPE_CHECKING:
    from pythonscad import Solid

T = X_TENSIONER
AXIS_Z = T.axle_z  #: idler axle, local z
FOOT_Z0 = BRACKET.base_t
BOARD_YC = sum(X_ENDSTOP.board_y) / 2
#: Outer face of the tensioner's end block (the screw head's seat), local x
BLOCK_X0 = X_DRIVE.idler_x - T.axle_x - slider_x0(T)
#: The endstop board's frame (origin, then its u, v, w axes), left bracket-local
BOARD: Matrix = frame_handle(
    [
        X_ENDSTOP.board_front_x,
        BOARD_YC,
        X_ENDSTOP.board_bottom_z - Y_AXIS.scs_top_z,
    ],
    [0, -1, 0],
    [1, 0, 0],
    [0, 0, 1],
)
#: Idler axle: bolt head seat on the slider's +y (rear) arm, shank toward -y (slider at mid-travel)
AXLE: Matrix = handle(
    [X_DRIVE.idler_x, X_BELT.y + T.head_side * T.width / 2, AXIS_Z], [T.axle_head_rot, 0, 0]
)
#: Tension screw: head seat on the end block's outboard face, shank toward +x
TENSION_SCREW: Matrix = handle([BLOCK_X0, X_BELT.y, T.screw_z], [0, -90, 0])


def x_idler_mount_installed() -> Solid:
    """The mount in the left bracket-local frame."""
    d = X_DRIVE
    x0 = d.foot_x0
    foot = cube([SCS10UU.width / 2 - x0, d.foot_y[1] - d.foot_y[0], d.foot_t]).translate(
        [x0, d.foot_y[0], FOOT_Z0]
    )
    # the board overhangs the foot's front edge: a shelf under it
    e = X_ENDSTOP
    shelf = cube(
        [e.board_x[1] - e.board_x[0] + 2, d.foot_y[0] - e.board_y[0] + 1 + EPS, d.foot_t]
    ).translate([e.board_x[0] - 1, e.board_y[0] - 1, FOOT_Z0])
    # the pad under the tensioner's rail, reaching forward and outboard of the main foot
    pad = cube(
        [d.idler_foot_x1 - BLOCK_X0, d.foot_y[0] + EPS - d.idler_foot_front_y, d.foot_t]
    ).translate([BLOCK_X0, d.idler_foot_front_y, FOOT_Z0])
    foot = foot | shelf | pad
    rail_len = slider_x0(T) + T.travel / 2 + T.plate_len
    rail = ridge(T, 0, rail_len).translate([BLOCK_X0, X_BELT.y, 0])
    block = end_block(T, FOOT_Z0).translate([BLOCK_X0, X_BELT.y, 0])
    # clamped by the rear bolt row; the front row's heads stay flush with the foot top (the
    # endstop plug needs the space), in clearance holes
    bolts = [
        cylinder(d=TOL.bolt_hole_d(5), h=d.foot_t + 2, fn=FN_HOLE).translate(
            [hx * SCS10UU.hole_pitch_x / 2, d.bolt_rows[1], FOOT_Z0 - 1]
        )
        for hx in (-1, 1)
    ] + [
        cylinder(d=metric(5).head_d + 1, h=d.foot_t + 2, fn=FN_HOLE).translate(
            [hx * SCS10UU.hole_pitch_x / 2, d.bolt_rows[0], FOOT_Z0 - 1]
        )
        for hx in (-1, 1)
    ]
    # endstop board screws: clearance holes through the foot, a nut pressed into a hex pocket in
    # its underside (the foot above it takes the pull)
    nut_t = TOL.nut_trap_h(3)
    board_holes = []
    for sv in (-1, 1):
        y = BOARD_YC + sv * ENDSTOP.hole_pitch / 2
        board_holes.append(
            cylinder(d=TOL.bolt_hole_d(3), h=d.foot_t + 2, fn=FN_HOLE).translate(
                [e.hole_x, y, FOOT_Z0 - 1]
            )
        )
        board_holes.append(
            cylinder(d=TOL.nut_trap_ac(3), h=nut_t + 1, fn=6).translate([e.hole_x, y, FOOT_Z0 - 1])
        )
    # solder relief: the board's underside has joints and pins sticking out up to 1.8 mm, so
    # the foot under it is recessed except for a land round each screw hole (T3.14)
    relief = cube(
        [e.board_x[1] - e.board_x[0] + 0.6, e.board_y[1] - e.board_y[0] + 0.6, e.relief_depth + 1]
    ).translate([e.board_x[0] - 0.3, e.board_y[0] - 0.3, FOOT_Z0 + d.foot_t - e.relief_depth])
    lands = [
        cylinder(d=e.land_d, h=e.relief_depth + 3, fn=FN_HOLE).translate(
            [
                e.hole_x,
                BOARD_YC + sv * ENDSTOP.hole_pitch / 2,
                FOOT_Z0 + d.foot_t - e.relief_depth - 1,
            ]
        )
        for sv in (-1, 1)
    ]
    relief = relief - union(*lands)
    mount = (foot - bolts - board_holes - relief) | rail | block
    return set_handles(mount, axle=AXLE, screw=TENSION_SCREW, board=BOARD)


def x_idler_mount() -> Solid:
    """Print orientation: foot on the bed."""
    return x_idler_mount_installed().translate([0, 0, -FOOT_Z0])
