"""X idler mount + belt tensioner (README §8 T3.4). Print ×1 (left gantry end).

Purpose: carries the X belt idler behind the beam at the left end of the gantry and
tensions the belt. The idler turns on an M5 axle that slides in a slot along x; an M3
screw from the inboard end pushes the axle outward to tension the belt, then the
axle nut locks it. The plate top carries the X endstop mount (x_endstop_mount.py).
The foot sits on the left gantry bracket's base over the rear SCS block and is
clamped by that block's 4 × M5 (they become M5×25).

  front view (from the beam)               side view
  ┌──────────────────┐ ← endstop mount     ┌──┐
  │  ═══slot═══ ←M3  │   inserts on top    │  │ plate
  │      ◯ idler     │                ◯═══╪  │ (axle M5 through
  └──────────────────┘                     │  │  spacer + slot)
  ────── foot ───────                     ─┴──┴── foot

Frame: LEFT bracket-local (``params.XDrive``), z = 0 on the SCS top face
(:func:`x_idler_mount_installed`); :func:`x_idler_mount` puts the foot on the bed.

Hardware: toothed 20T GT2 idler (Ø5 bore); 1 × M5×40 ISO 4762 + M5 washer + M5 nut
(nyloc) as the axle (head in front of the idler); 1 × x_idler_spacer (printed);
1 × M3 heat-set insert + 1 × M3×20 ISO 4762 (tension screw); 2 × M3 heat-set inserts
(endstop mount); 4 × M5×25 ISO 4762 replacing the rear SCS bolts of the left bracket.
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports.
"""

from pythonscad import cube, cylinder, hull, linear_extrude

from plotter_cad.geometry import EPS, FN_HOLE, teardrop, teardrop_x, teardrop_y
from plotter_cad.hardware import M3_INSERT, SCS10UU
from plotter_cad.params import BRACKET, TOL, X_BELT, X_DRIVE, Y_AXIS

AXIS_Z = X_BELT.pulley_axis_z - Y_AXIS.scs_top_z  #: idler axle, local z
FOOT_Z0 = BRACKET.base_t
TOP_Z = X_DRIVE.idler_top_z - Y_AXIS.scs_top_z  #: plate top, local z
PLATE_YC = X_DRIVE.plate_y0 + X_DRIVE.idler_plate_t / 2  #: plate mid-thickness (y)


def x_idler_mount_installed():
    """The mount in the left bracket-local frame."""
    d = X_DRIVE
    x0, x1 = d.idler_plate_x
    foot = cube([SCS10UU.width / 2 - x0, d.foot_y[1] - d.foot_y[0], d.foot_t]).translate(
        [x0, d.foot_y[0], FOOT_Z0]
    )
    plate = cube([x1 - x0, d.idler_plate_t, TOP_Z - FOOT_Z0]).translate([x0, d.plate_y0, FOOT_Z0])
    # rear SCS bolts
    bolts = [
        cylinder(d=TOL.bolt_hole_d(5), h=d.foot_t + 2, fn=FN_HOLE).translate(
            [hx * SCS10UU.hole_pitch_x / 2, y, FOOT_Z0 - 1]
        )
        for hx in (-1, 1)
        for y in d.bolt_rows
    ]
    # idler axle slot (along x)
    slot = hull(
        *(
            teardrop_y(TOL.bolt_hole_d(5), d.idler_plate_t + 2).translate(
                [d.idler_x + dx, PLATE_YC, AXIS_Z]
            )
            for dx in (-d.idler_slot / 2, d.idler_slot / 2)
        )
    )
    # tension screw: M3 insert at the inboard edge, clearance through to the slot
    insert = (
        linear_extrude(
            teardrop(M3_INSERT.hole_d).rotate([0, 0, -90]), height=TOL.insert_pocket_depth
        )  # point up
        .rotate([0, -90, 0])
        .translate([x1 + EPS, PLATE_YC, AXIS_Z])
    )
    screw = teardrop_x(TOL.bolt_hole_d(3), x1 - d.idler_x).translate(
        [(x1 + d.idler_x) / 2, PLATE_YC, AXIS_Z]
    )
    # endstop-mount inserts (top)
    endstop_inserts = [
        cylinder(d=M3_INSERT.hole_d, h=TOL.insert_pocket_depth, fn=FN_HOLE).translate(
            [x, PLATE_YC, TOP_Z - TOL.insert_pocket_depth + EPS]
        )
        for x in d.endstop_insert_x
    ]
    return (foot | plate) - bolts - slot - insert - screw - endstop_inserts


def x_idler_mount():
    """Print orientation: foot on the bed."""
    return x_idler_mount_installed().translate([0, 0, -FOOT_Z0])
