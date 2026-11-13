"""X idler mount + belt tensioner (STATUS.md T3.4). Print ×1 (left gantry end).

Purpose: carries the X belt idler behind the beam at the left end of the gantry and
tensions the belt. The idler turns on an M5 axle that slides in a slot along x; an M3
screw from the inboard end pushes the axle outward to tension the belt, then the
axle nut locks it. The plate top carries the X endstop mount (x_endstop_mount.py).
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
3 × M3 nuts (pressed in) + 1 × M3×20 ISO 4762 (tension screw) + 2 × M3×10 (endstop
mount); 4 × M5×25 ISO 4762 replacing the rear SCS bolts of the left bracket.
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import FN_HOLE, Matrix, handle, set_handles, teardrop_x, teardrop_y
from plotter_cad.hardware import SCS10UU
from plotter_cad.params import BRACKET, TOL, X_BELT, X_DRIVE, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid

AXIS_Z = X_BELT.pulley_axis_z - Y_AXIS.scs_top_z  #: idler axle, local z
FOOT_Z0 = BRACKET.base_t
TOP_Z = X_DRIVE.idler_top_z - Y_AXIS.scs_top_z  #: plate top, local z
SCREW_RELIEF = 4.0  #: hole below the endstop nuts for the screw tips
PLATE_YC = X_DRIVE.plate_y0 + X_DRIVE.idler_plate_t / 2  #: plate mid-thickness (y)
#: Idler axle: on the plate's front face (toward the beam), along +y through the slot's middle
AXLE: Matrix = handle([X_DRIVE.idler_x, X_DRIVE.plate_y0, AXIS_Z], [90, 0, 0])


def x_idler_mount_installed() -> Solid:
    """The mount in the left bracket-local frame."""
    d = X_DRIVE
    x0, x1 = d.idler_plate_x
    foot = cube([SCS10UU.width / 2 - x0, d.foot_y[1] - d.foot_y[0], d.foot_t]).translate(
        [x0, d.foot_y[0], FOOT_Z0]
    )
    plate = cube([x1 - x0, d.idler_plate_t, TOP_Z - FOOT_Z0]).translate([x0, d.plate_y0, FOOT_Z0])
    bolts = [
        cylinder(d=TOL.bolt_hole_d(5), h=d.foot_t + 2, fn=FN_HOLE).translate(
            [hx * SCS10UU.hole_pitch_x / 2, y, FOOT_Z0 - 1]
        )
        for hx in (-1, 1)
        for y in d.bolt_rows
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
    af, ac, nut_t = TOL.nut_trap_af(3), TOL.nut_trap_ac(3), TOL.nut_trap_h(3)
    nut_x1 = x1 - TOL.nut_wall
    tension_nut = cube([nut_t, af, TOP_Z - AXIS_Z + ac / 2 + 1]).translate(
        [nut_x1 - nut_t, PLATE_YC - af / 2, AXIS_Z - ac / 2]
    )
    screw = teardrop_x(TOL.bolt_hole_d(3), x1 + 2 - d.idler_x).translate(
        [(x1 + 2 + d.idler_x) / 2, PLATE_YC, AXIS_Z]
    )
    # endstop pad screws from the top: each nut is pressed into a slot from the rear face,
    # under a roof wall that takes the pull; a relief hole below takes the screw tip
    nut_z1 = TOP_Z - TOL.nut_wall
    endstop_nuts = [
        cube([af, d.plate_y0 + d.idler_plate_t - PLATE_YC + ac / 2 + 1, nut_t]).translate(
            [x - af / 2, PLATE_YC - ac / 2, nut_z1 - nut_t]
        )
        for x in d.endstop_screw_x
    ]
    endstop_holes = [
        cylinder(
            d=TOL.bolt_hole_d(3), h=TOL.nut_wall + nut_t + SCREW_RELIEF + 1, fn=FN_HOLE
        ).translate([x, PLATE_YC, nut_z1 - nut_t - SCREW_RELIEF])
        for x in d.endstop_screw_x
    ]
    mount = (foot | plate) - bolts - slot - tension_nut - screw - endstop_nuts - endstop_holes
    return set_handles(mount, axle=AXLE)


def x_idler_mount() -> Solid:
    """Print orientation: foot on the bed."""
    return x_idler_mount_installed().translate([0, 0, -FOOT_Z0])
