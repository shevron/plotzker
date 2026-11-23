"""Y idler mount with the floating idler's tower (STATUS.md T3.5, T3.23). Print ×1 left + ×1 right.

Purpose: carries the Y belt idler on the baseboard in front of the front SK10, in line with the
belt (30 mm outboard of the shaft), tensions the belt, and carries the Y endstop board. The
idler turns on an M5 axle held at both ends by the U-shaped :mod:`idler_slider`, which floats:
no rail, held only by an M3 screw along the belt line at the axle's height, through the tower at
the front of this foot (a plate with two side walls; see :mod:`floating_idler`). The screw's head
is reachable from the front. The foot is screwed to the baseboard outboard of the tower. A second
tower carries the endstop board in the plane of the gantry bracket's trigger screw (see
``params.YEndstopMount``): the screw tip, moving −y, pushes the lever toward the board 2 mm before
the end of travel; the screw's length sets the exact trip point.

  top view (left side)
  ┌───────────────┐ ← endstop tower (the board stands on its inboard face)
  │  ┌──┐ slider  │
  │  │▓ walls      │ ← the idler's tower walls along the slider
  │ ▓│ plate       │
  └──┴─M3 screw head, front

Frame: left side frame (``params.YDrive``: x from the shaft, machine y, z = baseboard
top); the part is printed foot down in the same orientation. The right-hand part is the
mirror image, except for the endstop tower's height and holes (the board is chiral, so the
lever hinge sits at the other end) and the idler tower's head pocket, which is on the other wall
so that both sides take the same unmirrored slider (:func:`idler_for`).

Hardware: see :mod:`idler_slider` (idler, M5×25 axle + nut, M3 nut) + 1 × M3×``Y_IDLER.screw_len``
ISO 4762 with a large M3 washer (tension screw, from the tower plate's front face); 2 × 4×25
countersunk wood screws into the baseboard (through 13 mm bosses on the foot, outboard of the
tower); the endstop board with 2 × M3×12 into 2 × M3 nuts pressed into the endstop tower's outboard
face.
Print: default profile (``profiles/default.toml``); foot down; no supports.

FEM (left): the screw's head pushes the tower plate with the idler's whole pull; held by the two
wood screws (their countersinks) and the baseboard under the foot; see :data:`PART_LEFT`. The right
mount has its own part (its endstop tower differs), with the same load path.
"""

from dataclasses import replace
from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE
from cadder.handles import frame_handle, handle, set_handles
from cadder.part import PrintedPart, Support
from cadder.regions import Box, Cylinder, Placement, bond_zone
from cadder.types import Matrix
from pythonscad import cube, cylinder, union

from plotzker.hardware import ENDSTOP
from plotzker.loads import Y_BELT_LOADS
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import TOL, WOOD_SCREW, Y_AXIS, Y_DRIVE, Y_ENDSTOP, Y_IDLER, FloatingIdler
from plotzker.parts.floating_idler import mount_fem, tower
from plotzker.parts.sk10_pocket import PocketEnd, sk10_pocket
from plotzker.parts.wood_screw import wood_screw_boss, wood_screw_hole
from plotzker.types import Side

if TYPE_CHECKING:
    from pythonscad import Solid

T = Y_IDLER
AXIS_Z = T.axle_z  #: idler axle height
SCREW_INSET = WOOD_SCREW.boss_d / 2 + 0.5  #: foot screws from the foot's ends (y)
#: The wood screws' x: bosses just outboard of the tower's wall
SCREW_X = Y_DRIVE.idler_foot_x0 + WOOD_SCREW.boss_d / 2 + 0.5


def idler_for(side: Side) -> FloatingIdler:
    """The idler as built in the left side frame for ``side``. The right side is that frame's
    mirror image, so to put the axle bolt's head on the same arm of the one (unmirrored) slider
    its tower has the head on the other wall in that frame."""
    return T if side is Side.LEFT else replace(T, head_side=-T.head_side)


def axle_handle(side: Side) -> Matrix:
    """Idler axle: bolt head seat on the head arm, shank toward the other arm (slider at
    mid-travel)."""
    head_x = Y_AXIS.belt_x - idler_for(side).head_side * T.width / 2  # tensioner y → side -x
    return handle([head_x, Y_DRIVE.idler_y, AXIS_Z], [0, -90 * idler_for(side).head_side, 0])


#: Tension screw: head seat on the tower plate's front face, shank toward +y
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
    # the tower's pad: under both walls, along the slider
    pad_x = (T.belt_pos - T.tower_half, T.belt_pos + T.tower_half)
    foot = foot | cube([pad_x[1] - pad_x[0], T.wall_end_s - y0, d.foot_t]).translate(
        [pad_x[0], y0, 0]
    )
    pocket_frame, pocket_cut = sk10_pocket(PocketEnd.FRONT, x1)
    idler_tower = to_side_frame(tower(idler_for(side)))
    screw_ys = (y0 + SCREW_INSET, y1 - SCREW_INSET)
    screw_x = SCREW_X
    holes = [wood_screw_hole(screw_x, y) for y in screw_ys]
    foot = foot | wood_screw_boss(screw_x, screw_ys[0]) | wood_screw_boss(screw_x, screw_ys[1])
    # endstop tower (not the idler's): the board stands against its inboard face
    u_z = -1 if side is Side.LEFT else 1
    z_top = e.board_z(u_z)[1]
    endstop_tower = cube(
        [e.tower_x[1] - e.tower_x[0], e.tower_y[1] - e.tower_y[0], z_top]
    ).translate([e.tower_x[0], e.tower_y[0], 0])
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
        (foot | endstop_tower | pocket_frame)
        - pocket_cut
        - holes
        - board_holes
        - (relief - union(*lands))
    ) | idler_tower
    board = frame_handle(
        [e.board_x0, e.board_front_y, zc], [0, 0, u_z], [0, 1, 0], [1, 0, 0]
    )  #: the endstop board's frame (the board is chiral: its u axis follows the side)
    return set_handles(mount, axle=axle_handle(side), tension_screw=TENSION_SCREW, board=board)


def y_idler_mount(side: Side = Side.LEFT) -> Solid:
    """The mount for one side, in print orientation (the right one is mirrored)."""
    mount = y_idler_mount_installed(side)
    return mount.mirror([1, 0, 0]) if side is Side.RIGHT else mount


# --- FEM definition (left mount, left side frame = print frame) -----------------------
PLACEMENT = Placement(1, (Y_AXIS.belt_x, Y_DRIVE.idler_block_y, 0.0))  #: the tensioner frame
_FOOT_X = (Y_DRIVE.idler_foot_x0, Y_DRIVE.idler_foot_x1)
_FOOT_Y = Y_DRIVE.idler_foot_y
_SCREW_X = SCREW_X
_SCREW_YS = (_FOOT_Y[0] + SCREW_INSET, _FOOT_Y[1] - SCREW_INSET)
#: The wood screws' heads seat on the countersink cones and the boss top around them
SCREW_SEATS = [
    Cylinder(
        center=(_SCREW_X, y, WOOD_SCREW.boss_t - WOOD_SCREW.sink_h / 2),
        axis=(0, 0, 1),
        radius=WOOD_SCREW.sink_d / 2,
        inner_radius=WOOD_SCREW.hole_d / 2,
        half_length=WOOD_SCREW.sink_h / 2 + 0.3,
        facing=(0, 0, 1),
        facing_tol_deg=60,
    )
    for y in _SCREW_YS
]
#: The foot's underside resting on the baseboard
FOOT_BEARING = Box(
    lo=(_FOOT_X[0], _FOOT_Y[0], -0.3), hi=(_FOOT_X[1], _FOOT_Y[1], 0.3), facing=(0, 0, -1)
)

#: Friction around each wood screw: the foot's underside is bonded to the baseboard
BOND_ZONES = [bond_zone((_SCREW_X, y, 0.0)) for y in _SCREW_YS]

PART_LEFT = PrintedPart(
    name="y_idler_mount_left",
    description="Y idler mount (left): foot on the baseboard with the floating idler's tower",
    build=lambda: y_idler_mount(Side.LEFT),
    analysis=y_idler_mount_installed,
    frame="installed",
    build_direction=(0, 0, 1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=mount_fem(
        Y_IDLER,
        PLACEMENT,
        Y_BELT_LOADS,
        "loads.Y_BELT_LOADS",
        supports=(
            Support(
                "wood_screw_front", SCREW_SEATS[0], "Front wood screw: countersink seat, fixed"
            ),
            Support("wood_screw_rear", SCREW_SEATS[1], "Rear wood screw: countersink seat, fixed"),
            Support(
                "foot_bearing",
                FOOT_BEARING,
                "Foot resting on the baseboard: held vertically",
                constrain=(False, False, True),
            ),
            Support("screw_zone_front", BOND_ZONES[0], "Friction round the front screw: bonded"),
            Support("screw_zone_rear", BOND_ZONES[1], "Friction round the rear screw: bonded"),
        ),
    ),
)

PART_RIGHT = PrintedPart(
    name="y_idler_mount_right",
    description="Y idler mount (right): foot on the baseboard (other-hand endstop tower)",
    build=lambda: y_idler_mount(Side.RIGHT),
    analysis=lambda: y_idler_mount_installed(Side.RIGHT),
    frame="installed",
    build_direction=(0, 0, 1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=PART_LEFT.fem,
)
