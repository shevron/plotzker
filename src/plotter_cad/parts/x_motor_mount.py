"""X motor mount (README §8 T3.4). Print ×1 (right gantry end).

Purpose: holds the X NEMA17 behind the beam at the right end of the gantry, shaft
pointing forward (−y) so the 20T pulley sits on the X belt line. The foot sits on the
right gantry bracket's base over the rear SCS block and is clamped by that block's
4 × M5 (they become M5×25). A rib under the motor carries its weight.

  side view (looking along x)          top view
       plate                               ┌─motor─┐
  pulley │┌──────┐                    beam │       │
  ◯═════ ││ motor│                    ═════│plate  │
         │└──────┘                         ├──rib──┤
  ───foot┴──rib───  on the bracket base    └─foot──┘

Frame: designed in the LEFT bracket-local frame (``params.XDrive``), z = 0 on the SCS
top face (:func:`x_motor_mount_left`). The printed part is the mirror image (it goes
on the right end): :func:`x_motor_mount`.

Hardware: 4 × M3×10 ISO 4762 (motor); 4 × M5×25 ISO 4762 replacing the rear SCS bolts
of the right bracket; 20T GT2 pulley on the motor (hub toward the motor, belt center
at the X belt line — slide it on the shaft to align with the idler).
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from plotter_cad.geometry import EPS, FN_HOLE, teardrop_y
from plotter_cad.hardware import NEMA17, SCS10UU
from plotter_cad.params import BRACKET, TOL, X_BELT, X_DRIVE, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid

AXIS_Z = X_BELT.pulley_axis_z - Y_AXIS.scs_top_z  #: motor axis, local z
FOOT_Z0 = BRACKET.base_t  #: the foot sits on the bracket base
PLATE_X = (X_DRIVE.motor_x - NEMA17.width / 2, X_DRIVE.motor_x + NEMA17.width / 2)
PLATE_TOP = AXIS_Z + NEMA17.width / 2
MOTOR_BOTTOM = AXIS_Z - NEMA17.width / 2


def x_motor_mount_left() -> Solid:
    """The mount as designed, in the left bracket-local frame (not printed like this)."""
    d = X_DRIVE
    foot_x0 = min(-SCS10UU.width / 2 - 1, PLATE_X[0])
    foot_x1 = max(SCS10UU.width / 2, PLATE_X[1])
    foot = cube([foot_x1 - foot_x0, d.foot_y[1] - d.foot_y[0], d.foot_t]).translate(
        [foot_x0, d.foot_y[0], FOOT_Z0]
    )
    plate = cube([NEMA17.width, d.motor_plate_t, PLATE_TOP - FOOT_Z0]).translate(
        [PLATE_X[0], d.plate_y0, FOOT_Z0]
    )
    rib = cube(
        [d.motor_rib_t, d.foot_y[1] - d.motor_face_y + EPS, MOTOR_BOTTOM - 0.5 - FOOT_Z0]
    ).translate([d.motor_x - d.motor_rib_t / 2, d.motor_face_y - EPS, FOOT_Z0])
    bolts = [
        cylinder(d=TOL.bolt_hole_d(5), h=d.foot_t + 2, fn=FN_HOLE).translate(
            [hx * SCS10UU.hole_pitch_x / 2, y, FOOT_Z0 - 1]
        )
        for hx in (-1, 1)
        for y in d.bolt_rows
    ]
    plate_mid_y = d.plate_y0 + d.motor_plate_t / 2
    boss = teardrop_y(NEMA17.boss_d + 0.4, d.motor_plate_t + 2).translate(
        [d.motor_x, plate_mid_y, AXIS_Z]
    )
    screws = [
        teardrop_y(TOL.bolt_hole_d(3), d.motor_plate_t + 2).translate(
            [
                d.motor_x + dx * NEMA17.hole_pitch / 2,
                plate_mid_y,
                AXIS_Z + dz * NEMA17.hole_pitch / 2,
            ]
        )
        for dx in (-1, 1)
        for dz in (-1, 1)
    ]
    return (foot | plate | rib) - bolts - boss - screws


def x_motor_mount() -> Solid:
    """The printed part (right end) = mirror image, foot on the bed."""
    return x_motor_mount_left().mirror([1, 0, 0]).translate([0, 0, -FOOT_Z0])
