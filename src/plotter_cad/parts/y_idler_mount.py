"""Y idler mount with the belt tensioner's rail (STATUS.md T3.5, T3.17). Print ×1 left + ×1 right.

Purpose: carries the Y belt idler on the baseboard in front of the front SK10, in line with the
belt (30 mm outboard of the shaft), tensions the belt, and carries the Y endstop board. The
idler turns on an M5 axle held at both ends by the U-shaped :mod:`y_idler_slider`, which rides on
a dovetail ridge on this foot (the rail); an M3 screw through the end block at the front pulls
the slider forward to tension the belt (the head is reachable from the front). The generic design
is :mod:`tension_idler`. The foot is screwed to the baseboard. A tower carries the endstop board
in the plane of the gantry bracket's trigger screw (see ``params.YEndstopMount``): the screw tip,
moving −y, pushes the lever toward the board 2 mm before the end of travel; the screw's length
sets the exact trip point.

  top view (left side)
  ┌───────────────┐ ← tower (endstop board stands on its inboard face)
  │  ┌──┐ slider  │
  │  │▓ ═ ridge ═ │ ← rail along y, belt line x = belt_x
  │ ▓│ end block  │
  └──┴─M3 screw head, front

Frame: left side frame (``params.YDrive``: x from the shaft, machine y, z = baseboard
top); the part is printed foot down in the same orientation. The right-hand part is the
mirror image, except for the endstop tower's height and holes: the board is chiral, so
the lever hinge sits at the other end (:func:`y_idler_mount`).

Hardware: see :mod:`y_idler_slider` (idler, M5×25 axle + nut, M3 nut) + 1 × M3×25 ISO 4762
(tension screw, from the end block's front face); 2 × 4×25 countersunk wood screws into the
baseboard (through 9 mm bosses on the foot); the endstop board with 2 × M3×12 into 2 × M3 nuts
pressed into the tower's outboard face.
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports (the ridge's 45°
flanks self-support).
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, union

from plotter_cad.geometry import FN_HOLE, frame_handle, handle, set_handles
from plotter_cad.hardware import ENDSTOP
from plotter_cad.params import TOL, WOOD_SCREW, Y_AXIS, Y_DRIVE, Y_ENDSTOP, Y_TENSIONER
from plotter_cad.parts.sk10_pocket import PocketEnd, sk10_pocket
from plotter_cad.parts.tension_idler import end_block, ridge, slider_x0
from plotter_cad.parts.wood_screw import wood_screw_boss, wood_screw_hole
from plotter_cad.types import Matrix, Side

if TYPE_CHECKING:
    from pythonscad import Solid

T = Y_TENSIONER
AXIS_Z = T.axle_z  #: idler axle height
SCREW_INSET = WOOD_SCREW.boss_d / 2 + 0.5  #: foot screws from the foot's ends (y)
#: Idler axle: bolt head seat on the slider's inboard arm, shank toward -x (slider at mid-travel)
AXLE: Matrix = handle([Y_AXIS.belt_x + T.width / 2, Y_DRIVE.idler_y, AXIS_Z], [0, 90, 0])
#: Tension screw: head seat on the end block's front face, shank toward +y
TENSION_SCREW: Matrix = handle([Y_AXIS.belt_x, Y_DRIVE.idler_block_y, T.screw_z], [90, 0, 0])


def to_side_frame(solid: Solid) -> Solid:
    """A solid in the tensioner's frame (x along the slide, y along the axle) in the left side
    frame: slide direction +y, axle direction -x, end block's front face at ``idler_block_y``."""
    return solid.rotate([0, 0, 90]).translate([Y_AXIS.belt_x, Y_DRIVE.idler_block_y, 0])


def y_idler_mount_installed(side: Side = Side.LEFT) -> Solid:
    """The mount in the left side frame (``side`` selects the endstop board's orientation)."""
    d = Y_DRIVE
    e = Y_ENDSTOP
    x0, x1 = d.idler_foot_x0, d.idler_foot_x1
    y0, y1 = d.idler_foot_y
    foot = cube([x1 - x0, y1 - y0, d.foot_t]).translate([x0, y0, 0])
    pocket_frame, pocket_cut = sk10_pocket(PocketEnd.FRONT, x1)
    rail_len = slider_x0(T) + T.travel / 2 + T.plate_len
    rail = to_side_frame(ridge(T, 0, rail_len))
    block = to_side_frame(end_block(T, 0))
    screw_ys = (y0 + SCREW_INSET, y1 - SCREW_INSET)
    screw_x = d.idler_foot_x0 + d.idler_foot_out / 2
    holes = [wood_screw_hole(screw_x, y) for y in screw_ys]
    foot = foot | wood_screw_boss(screw_x, screw_ys[0]) | wood_screw_boss(screw_x, screw_ys[1])
    # endstop tower: the board stands against its inboard face
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
    # solder relief: only a land round each board screw hole touches the board (T3.14)
    zb0, zb1 = e.board_z(u_z)
    relief = cube(
        [e.relief_depth + 1, e.board_y[1] - e.board_y[0] + 0.6, zb1 - zb0 - 0.5]
    ).translate([e.board_x0 - e.relief_depth, e.board_y[0] - 0.3, zb0 - 0.3])
    lands = [
        cylinder(d=e.land_d, h=e.relief_depth + 3, fn=FN_HOLE)
        .rotate([0, 90, 0])
        .translate(
            [
                e.board_x0 - e.relief_depth - 1,
                e.board_front_y + ENDSTOP.hole_v,
                zc + sz * ENDSTOP.hole_pitch / 2,
            ]
        )
        for sz in (-1, 1)
    ]
    mount = (
        (
            (foot | tower | pocket_frame)
            - pocket_cut
            - holes
            - board_holes
            - (relief - union(*lands))
        )
        | rail
        | block
    )
    board = frame_handle(
        [e.board_x0, e.board_front_y, zc], [0, 0, u_z], [0, 1, 0], [1, 0, 0]
    )  #: the endstop board's frame (the board is chiral: its u axis follows the side)
    return set_handles(mount, axle=AXLE, tension_screw=TENSION_SCREW, board=board)


def y_idler_mount(side: Side = Side.LEFT) -> Solid:
    """The mount for one side, in print orientation (the right one is mirrored)."""
    mount = y_idler_mount_installed(side)
    return mount.mirror([1, 0, 0]) if side is Side.RIGHT else mount
