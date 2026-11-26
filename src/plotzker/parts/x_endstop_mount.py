"""X endstop mount (STATUS.md T3.14, T3.22). Print ×1 (left end).

Purpose: a small foot that carries the X endstop board (Creality-type microswitch board) on the
left gantry bracket's base over the rear SCS block, clamped by that block's rear row of M5 (those 2
heads sit on the foot; they become M5×25). It used to be the idler mount's foot; the idler's
tower is part of the bracket now (:mod:`gantry_end_bracket`), so this part carries no belt load.

  top view

      ┌─ board ──────┐
      │  ◯       ◯   │   ← 2 × M3 (nuts pressed into the foot's underside), solder relief
   ┌──┴──────────────┴──┐
   │  foot (clamped     │
   └────────────────────┘

Frame: LEFT bracket-local (``params.XDrive``), z = 0 on the SCS top face
(:func:`x_endstop_mount_installed`); :func:`x_endstop_mount` puts the foot on the bed.

Hardware: 2 × M3 nuts (pressed into the foot's underside) + 2 × M3×6 (endstop board);
2 × M5×25 ISO 4762 replacing the rear row of the left bracket's rear SCS bolts.
Print: default profile (``profiles/default.toml``); foot down; no supports.

FEM: not structural (the board's loads are a few newtons at most).
"""

from typing import TYPE_CHECKING

from cadder.geometry import EPS, FN_HOLE
from cadder.handles import frame_handle, set_handles
from cadder.hardware import SCS10UU, metric
from cadder.part import PrintedPart
from cadder.types import Matrix
from pythonscad import cube, cylinder, union

from plotzker.hardware import ENDSTOP
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import BRACKET, TOL, X_DRIVE, X_ENDSTOP, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid

FOOT_Z0 = BRACKET.base_t
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


def x_endstop_mount_installed() -> Solid:
    """The mount in the left bracket-local frame."""
    d = X_DRIVE
    x0 = d.foot_x0
    foot = cube([SCS10UU.width / 2 - x0, d.foot_y[1] - d.foot_y[0], d.foot_t]).translate([x0, d.foot_y[0], FOOT_Z0])
    # the board overhangs the foot's front edge: a shelf under it
    e = X_ENDSTOP
    shelf = cube([e.board_x[1] - e.board_x[0] + 2, d.foot_y[0] - e.board_y[0] + 1 + EPS, d.foot_t]).translate(
        [e.board_x[0] - 1, e.board_y[0] - 1, FOOT_Z0]
    )
    foot = foot | shelf
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
            cylinder(d=TOL.bolt_hole_d(3), h=d.foot_t + 2, fn=FN_HOLE).translate([e.hole_x, y, FOOT_Z0 - 1])
        )
        board_holes.append(cylinder(d=TOL.nut_trap_ac(3), h=nut_t + 1, fn=6).translate([e.hole_x, y, FOOT_Z0 - 1]))
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
    mount = foot - bolts - board_holes - relief
    return set_handles(mount, board=BOARD)


def x_endstop_mount() -> Solid:
    """Print orientation: foot on the bed."""
    return x_endstop_mount_installed().translate([0, 0, -FOOT_Z0])


PART = PrintedPart(
    name="x_endstop_mount",
    description="X endstop mount: foot under the endstop board, clamped by the rear bolts",
    build=x_endstop_mount,
    analysis=x_endstop_mount_installed,
    frame="installed",
    build_direction=(0, 0, 1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    structural=False,
)
