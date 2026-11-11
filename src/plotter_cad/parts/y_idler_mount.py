"""Y idler mount + belt tensioner (STATUS.md T3.5). Print ×1 left + ×1 right.

Purpose: carries the Y belt idler on the baseboard in front of the front SK10, in line
with the belt (30 mm outboard of the shaft), tensions the belt, and carries the Y endstop
board. The idler turns on an M5 axle held by a plate outboard of it; the axle slides in a
slot along y. An M3 screw from the rear edge pushes the axle forward to tension the belt;
the axle nut then locks it. The foot is screwed to the baseboard. A tower on the plate
carries the endstop board in the plane of the gantry bracket's trigger screw (see
``params.YEndstopMount``): the screw tip, moving −y, pushes the lever toward the board
2 mm before the end of travel; the screw's length sets the exact trip point.

  top view (left side)                          side view (looking along +x)
  ┌──────┐ ← rear edge, tension screw head      ┌────┐ plate
  │ slot │ ← M5 axle slides here (±4 mm)    ◯═══╡    │  axle through
  │      │                                      └────┘  the plate
  ├──────┘                                    ──foot──   (nut outboard)
  └ foot (2 × M4 wood screws)

Frame: left side frame (``params.YDrive``: x from the shaft, machine y, z = baseboard
top); the part is printed foot down in the same orientation. The right-hand part is the
mirror image, except for the endstop tower's height and pilots: the board is chiral, so
the lever hinge sits at the other end (:func:`y_idler_mount`).

Hardware: toothed 20T GT2 idler (Ø5 bore); 1 × M5×30 ISO 4762 + M5 nut (nyloc) + 2 × M5
washers (one each side of the idler) as the axle, head inboard of the idler; 1 × M3 heat-set
insert + 1 × M3×20 ISO 4762 (tension screw); 2 × M4 wood screws into the baseboard;
the endstop board with 2 × M3×6 (or its own screws) self-tapping into the Ø2.6 pilots.
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull, linear_extrude

from plotter_cad.geometry import EPS, FN_HOLE, teardrop, teardrop_x, teardrop_y
from plotter_cad.hardware import ENDSTOP, M3_INSERT, metric
from plotter_cad.params import TOL, Y_AXIS, Y_DRIVE, Y_ENDSTOP
from plotter_cad.parts.gantry_end_bracket import Side
from plotter_cad.parts.sk10_pocket import PocketEnd, sk10_pocket

if TYPE_CHECKING:
    from pythonscad import Solid

AXIS_Z = Y_AXIS.pulley_axis_z  #: idler axle height
SCREW_M = 4  #: wood screws into the baseboard
PILOT_D = 2.6  #: M3 self-tapping into the endstop board's holes
PILOT_DEPTH = 5  #: M3×6 through the 1.5 mm board


def y_idler_mount_installed(side: Side = Side.LEFT) -> Solid:
    """The mount in the left side frame (``side`` selects the endstop board's orientation)."""
    d = Y_DRIVE
    x0, x1 = d.idler_plate_x
    y0, y1 = d.idler_plate_y
    plate_cx = (x0 + x1) / 2
    foot = cube([x1 - d.idler_foot_x0, y1 - y0, d.foot_t]).translate([d.idler_foot_x0, y0, 0])
    pocket_frame, pocket_cut = sk10_pocket(PocketEnd.FRONT, x1)
    plate = cube([x1 - x0, y1 - y0, d.idler_top_z]).translate([x0, y0, 0])
    slot = hull(
        *(
            teardrop_x(TOL.bolt_hole_d(5), d.idler_plate_t + 2).translate(
                [plate_cx, d.idler_y + dy, AXIS_Z]
            )
            for dy in (-d.idler_slot / 2, d.idler_slot / 2)
        )
    )
    # tension screw: M3 insert pressed in from the rear edge, clearance through to the slot
    insert = (
        linear_extrude(teardrop(M3_INSERT.hole_d), height=TOL.insert_pocket_depth + EPS)
        .rotate([90, 0, 0])
        .translate([plate_cx, y1 + EPS, AXIS_Z])
    )
    screw_y1 = y1 - TOL.insert_pocket_depth + 1
    screw = teardrop_y(TOL.bolt_hole_d(3), screw_y1 - d.idler_y).translate(
        [plate_cx, (screw_y1 + d.idler_y) / 2, AXIS_Z]
    )
    holes = []
    for y in (y0 + 6, y1 - 6):
        x = d.idler_foot_x0 + d.idler_foot_out / 2
        holes.append(
            cylinder(d=TOL.bolt_hole_d(SCREW_M), h=d.foot_t + 2, fn=FN_HOLE).translate([x, y, -1])
        )
        holes.append(
            cylinder(d=TOL.cbore_d(SCREW_M), h=metric(SCREW_M).head_h + 1, fn=FN_HOLE).translate(
                [x, y, d.foot_t - metric(SCREW_M).head_h]
            )
        )
    # endstop tower: the board stands against its inboard face
    e = Y_ENDSTOP
    u_z = -1 if side is Side.LEFT else 1
    z_top = e.board_z(u_z)[1]
    tower = cube([e.tower_x[1] - e.tower_x[0], e.tower_y[1] - e.tower_y[0], z_top]).translate(
        [e.tower_x[0], e.tower_y[0], 0]
    )
    zc = e.board_z_center(u_z)
    pilots = [
        cylinder(d=PILOT_D, h=PILOT_DEPTH + 1, fn=FN_HOLE)
        .rotate([0, -90, 0])
        .translate(
            [e.board_x0 + 1, e.board_front_y + ENDSTOP.hole_v, zc + sz * ENDSTOP.hole_pitch / 2]
        )
        for sz in (-1, 1)
    ]
    return (
        (foot | plate | tower | pocket_frame) - pocket_cut - slot - insert - screw - holes - pilots
    )


def y_idler_mount(side: Side = Side.LEFT) -> Solid:
    """The mount for one side, in print orientation (the right one is mirrored)."""
    mount = y_idler_mount_installed(side)
    return mount.mirror([1, 0, 0]) if side is Side.RIGHT else mount
