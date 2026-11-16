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
  └ foot (2 × 4×25 countersunk wood screws)

Frame: left side frame (``params.YDrive``: x from the shaft, machine y, z = baseboard
top); the part is printed foot down in the same orientation. The right-hand part is the
mirror image, except for the endstop tower's height and holes: the board is chiral, so
the lever hinge sits at the other end (:func:`y_idler_mount`).

Hardware: toothed 20T GT2 idler (Ø5 bore); 1 × M5×30 ISO 4762 + M5 nut (nyloc) + 2 × M5
washers (one each side of the idler) as the axle, head inboard of the idler; 1 × M3 nut
(pressed into the top slot) + 1 × M3×20 ISO 4762 (tension screw); 2 × 4×25 countersunk wood
screws into the baseboard (through 9 mm bosses on the foot);
the endstop board with 2 × M3×12 into 2 × M3 nuts pressed into the tower's outboard face.
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import (
    FN_HOLE,
    Matrix,
    frame_handle,
    handle,
    set_handles,
    teardrop_x,
    teardrop_y,
)
from plotter_cad.hardware import ENDSTOP
from plotter_cad.nut_slot import nut_slot
from plotter_cad.params import TOL, WOOD_SCREW, Y_AXIS, Y_DRIVE, Y_ENDSTOP
from plotter_cad.parts.gantry_end_bracket import Side
from plotter_cad.parts.sk10_pocket import PocketEnd, sk10_pocket
from plotter_cad.parts.wood_screw import wood_screw_boss, wood_screw_hole

if TYPE_CHECKING:
    from pythonscad import Solid

AXIS_Z = Y_AXIS.pulley_axis_z  #: idler axle height
SCREW_INSET = WOOD_SCREW.boss_d / 2 + 0.5  #: foot screws from the plate ends (y)

_PLATE_CX = sum(Y_DRIVE.idler_plate_x) / 2
#: Idler axle: on the plate's inboard face, along +x, in the middle of the slot
AXLE: Matrix = handle([Y_DRIVE.idler_plate_x[1], Y_DRIVE.idler_y, AXIS_Z], [0, 90, 0])
#: Tension screw: head on the plate's rear edge, along +y toward the slot
TENSION_SCREW: Matrix = handle([_PLATE_CX, Y_DRIVE.idler_plate_y[1], AXIS_Z], [-90, 0, 0])


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
    # tension screw: M3 clearance hole from the rear edge to the slot; the nut is pressed
    # into a slot from the top, behind a wall that takes the thrust
    nut_t = TOL.nut_trap_h(3)
    nut_y1 = y1 - TOL.nut_wall
    tension_nut = nut_slot(3, d.idler_top_z - AXIS_Z + 1, "y", "+z").translate(
        [plate_cx, nut_y1 - nut_t / 2, AXIS_Z]
    )
    screw = teardrop_y(TOL.bolt_hole_d(3), y1 + 2 - d.idler_y).translate(
        [plate_cx, (y1 + 2 + d.idler_y) / 2, AXIS_Z]
    )
    screw_ys = (y0 + SCREW_INSET, y1 - SCREW_INSET)
    screw_x = d.idler_foot_x0 + d.idler_foot_out / 2
    holes = [wood_screw_hole(screw_x, y) for y in screw_ys]
    foot = foot | wood_screw_boss(screw_x, screw_ys[0]) | wood_screw_boss(screw_x, screw_ys[1])
    # endstop tower: the board stands against its inboard face
    e = Y_ENDSTOP
    u_z = -1 if side is Side.LEFT else 1
    z_top = e.board_z(u_z)[1]
    tower = cube([e.tower_x[1] - e.tower_x[0], e.tower_y[1] - e.tower_y[0], z_top]).translate(
        [e.tower_x[0], e.tower_y[0], 0]
    )
    zc = e.board_z_center(u_z)
    board_holes = []
    for sz in (-1, 1):
        y, z = e.board_front_y + ENDSTOP.hole_v, zc + sz * ENDSTOP.hole_pitch / 2
        # M3 clearance through the tower, and a hex pocket for the nut in its outboard face
        # (corners up: no support needed)
        board_holes.append(
            cylinder(d=TOL.bolt_hole_d(3), h=e.tower_x[1] - e.tower_x[0] + 2, fn=FN_HOLE)
            .rotate([0, 90, 0])
            .translate([e.tower_x[0] - 1, y, z])
        )
        board_holes.append(
            cylinder(d=TOL.nut_trap_ac(3), h=TOL.nut_trap_h(3) + 1, fn=6)
            .rotate([0, 90, 0])
            .translate([e.tower_x[0] - 1, y, z])
        )
    mount = (
        (foot | plate | tower | pocket_frame)
        - pocket_cut
        - slot
        - tension_nut
        - screw
        - holes
        - board_holes
    )
    board = frame_handle(
        [e.board_x0, e.board_front_y, zc], [0, 0, u_z], [0, 1, 0], [1, 0, 0]
    )  #: the endstop board's frame (the board is chiral: its u axis follows the side)
    return set_handles(mount, axle=AXLE, tension_screw=TENSION_SCREW, board=board)


def y_idler_mount(side: Side = Side.LEFT) -> Solid:
    """The mount for one side, in print orientation (the right one is mirrored)."""
    mount = y_idler_mount_installed(side)
    return mount.mirror([1, 0, 0]) if side is Side.RIGHT else mount
