"""X idler mount + belt tensioner (STATUS.md T3.4). Print ×1 (left gantry end).

Purpose: carries the X belt idler behind the beam at the left end of the gantry and
tensions the belt. The idler turns on an M5 axle that slides in a slot along x; an M3
screw from the inboard end pushes the axle outward to tension the belt, then the
axle nut locks it. The foot, inboard of the plate, carries the X endstop board.
The foot sits on the left gantry bracket's base over the rear SCS block and is
clamped by that block's 4 × M5 (they become M5×25).

  front view (from the beam)               side view
  ┌──────────────────┐ ← endstop mount     ┌──┐
  │  ═══slot═══ ←M3  │   nuts, rear face  │  │ plate
  │      ◯ idler     │                ◯═══╪  │ (axle M5 through
  └──────────────────┘                     │  │  spacer + slot)
  ────── foot ───────                     ─┴──┴── foot

Frame: LEFT bracket-local (``params.XDrive``), z = 0 on the SCS top face
(:func:`x_idler_mount_installed`); :func:`x_idler_mount` puts the foot on the bed.

Hardware: toothed 20T GT2 idler (Ø5 bore); 1 × M5×40 ISO 4762 + M5 washer + M5 nut
(nyloc) as the axle (head in front of the idler); 1 × x_idler_spacer (printed);
1 × M3 nut (pressed in) + 1 × M3×20 ISO 4762 (tension screw); 2 × M3 nuts (pressed
into the foot's underside) + 2 × M3×6 (endstop board); 4 × M5×25 ISO 4762 replacing the
rear SCS bolts of the left bracket (rear row only; the front row's heads sit flush with the
foot).
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import (
    EPS,
    FN_HOLE,
    Matrix,
    frame_handle,
    handle,
    set_handles,
    teardrop_x,
    teardrop_y,
)
from plotter_cad.hardware import ENDSTOP, SCS10UU, metric
from plotter_cad.nut_slot import nut_slot
from plotter_cad.params import BRACKET, TOL, X_BELT, X_DRIVE, X_ENDSTOP, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid

AXIS_Z = X_BELT.pulley_axis_z - Y_AXIS.scs_top_z  #: idler axle, local z
FOOT_Z0 = BRACKET.base_t
TOP_Z = X_DRIVE.idler_top_z - Y_AXIS.scs_top_z  #: plate top, local z
PLATE_YC = X_DRIVE.plate_y0 + X_DRIVE.idler_plate_t / 2  #: plate mid-thickness (y)
BOARD_YC = sum(X_ENDSTOP.board_y) / 2
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
#: Idler axle: on the plate's front face (toward the beam), along +y through the slot's middle
AXLE: Matrix = handle([X_DRIVE.idler_x, X_DRIVE.plate_y0, AXIS_Z], [90, 0, 0])


def x_idler_mount_installed() -> Solid:
    """The mount in the left bracket-local frame."""
    d = X_DRIVE
    x0, x1 = d.idler_plate_x
    foot = cube([SCS10UU.width / 2 - x0, d.foot_y[1] - d.foot_y[0], d.foot_t]).translate(
        [x0, d.foot_y[0], FOOT_Z0]
    )
    # the board overhangs the foot's front edge: a shelf under it
    e = X_ENDSTOP
    shelf = cube(
        [e.board_x[1] - e.board_x[0] + 2, d.foot_y[0] - e.board_y[0] + 1 + EPS, d.foot_t]
    ).translate([e.board_x[0] - 1, e.board_y[0] - 1, FOOT_Z0])
    foot = foot | shelf
    plate = cube([x1 - x0, d.idler_plate_t, TOP_Z - FOOT_Z0]).translate([x0, d.plate_y0, FOOT_Z0])
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
    slot = hull(
        *(
            teardrop_y(TOL.bolt_hole_d(5), d.idler_plate_t + 2).translate(
                [d.idler_x + dx, PLATE_YC, AXIS_Z]
            )
            for dx in (-d.idler_slot / 2, d.idler_slot / 2)
        )
    )
    # tension screw: M3 clearance hole from the inboard edge to the slot; the nut is pressed
    # into a slot from the top, behind a wall that takes the thrust
    nut_t = TOL.nut_trap_h(3)
    nut_x1 = x1 - TOL.nut_wall
    tension_nut = nut_slot(3, TOP_Z - AXIS_Z + 1, "x", "+z").translate(
        [nut_x1 - nut_t / 2, PLATE_YC, AXIS_Z]
    )
    screw = teardrop_x(TOL.bolt_hole_d(3), x1 + 2 - d.idler_x).translate(
        [(x1 + 2 + d.idler_x) / 2, PLATE_YC, AXIS_Z]
    )
    # endstop board screws: clearance holes through the foot, a nut pressed into a hex pocket in
    # its underside (the foot above it takes the pull)
    e = X_ENDSTOP
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
    mount = (foot | plate) - bolts - slot - tension_nut - screw - board_holes
    return set_handles(mount, axle=AXLE, board=BOARD)


def x_idler_mount() -> Solid:
    """Print orientation: foot on the bed."""
    return x_idler_mount_installed().translate([0, 0, -FOOT_Z0])
