"""X− endstop switch mount (STATUS.md T3.4, redone in T3.5 for the measured board). Print ×1.

Purpose: carries the X endstop board (Creality type) flat above the X idler mount at the
left end of the gantry, components up, front edge toward +x. At the carriage's left end
of travel the head of its trigger screw pushes the lever (hinged at the +y end of the
switch, tip toward −y) toward the board. The pad sits on top of the idler plate; slots give
±4 mm of x adjustment on top of the trigger screw's own.

  top view                                   side view (from −y)
  ┌ pad ──────────────────────┐              board  ┌──────┐◄ trigger head
  │ ⊙slot  ⊙slot   ┌board────┐│              ────────┴──────┴── pad (counterbored)
  └───────────────┴└─────────┘┘              ──── idler plate top ────

Frame: LEFT bracket-local (``params.XDrive``), z = 0 on the SCS top face
(:func:`x_endstop_mount_installed`); :func:`x_endstop_mount` puts the pad bottom on the bed.
The board position follows ``hardware.ENDSTOP`` (measured) and ``params.XEndstopMount``.

Hardware: 2 × M3×10 ISO 4762 into nuts pressed into the idler mount (heads in the pad's
counterbores); 2 × M3×6 through the board into 2 × M3 nuts pressed into hex pockets in
the pad's underside.
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; pad bottom down; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import FN_HOLE, Matrix, frame_handle, set_handles
from plotter_cad.hardware import ENDSTOP, metric
from plotter_cad.params import TOL, X_DRIVE, X_ENDSTOP, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid

PAD_Z = (X_ENDSTOP.pad_z[0] - Y_AXIS.scs_top_z, X_ENDSTOP.pad_z[1] - Y_AXIS.scs_top_z)
PLATE_YC = X_DRIVE.plate_y0 + X_DRIVE.idler_plate_t / 2
BOARD_YC = sum(X_ENDSTOP.board_y) / 2
_EDGE = TOL.cbore_d(3) / 2 + TOL.min_wall  #: slot end to pad edge
#: The endstop board's frame (origin, then its u, v, w axes), left bracket-local
BOARD: Matrix = frame_handle(
    [
        X_ENDSTOP.board_front_x,
        sum(X_ENDSTOP.board_y) / 2,
        X_ENDSTOP.board_bottom_z - Y_AXIS.scs_top_z,
    ],
    [0, -1, 0],
    [1, 0, 0],
    [0, 0, 1],
)
PAD_X = (X_DRIVE.endstop_screw_x[0] - X_ENDSTOP.pad_slot - _EDGE, X_ENDSTOP.board_front_x)
PAD_Y = (
    X_ENDSTOP.board_y[0] - X_ENDSTOP.pad_margin,
    max(X_ENDSTOP.board_y[1] + X_ENDSTOP.pad_margin, PLATE_YC + _EDGE),
)


def x_endstop_mount_installed() -> Solid:
    """The mount in the left bracket-local frame."""
    e = X_ENDSTOP
    pad = cube([PAD_X[1] - PAD_X[0], PAD_Y[1] - PAD_Y[0], e.pad_t]).translate(
        [PAD_X[0], PAD_Y[0], PAD_Z[0]]
    )
    head_h = metric(3).head_h + 0.5
    slots = []
    for x in X_DRIVE.endstop_screw_x:
        for d, z0, h in (
            (TOL.bolt_hole_d(3), PAD_Z[0] - 1, e.pad_t + 2),
            (TOL.cbore_d(3), PAD_Z[1] - head_h, head_h + 1),
        ):
            slots.append(
                hull(
                    *(
                        cylinder(d=d, h=h, fn=FN_HOLE).translate([x + dx, PLATE_YC, z0])
                        for dx in (-e.pad_slot, e.pad_slot)
                    )
                )
            )
    # board screws: clearance holes through the pad, a nut pressed into a hex pocket in the
    # pad's underside (the roof above it takes the pull)
    nut_t = TOL.nut_trap_h(3)
    board_holes = []
    for sv in (-1, 1):
        y = BOARD_YC + sv * ENDSTOP.hole_pitch / 2
        board_holes.append(
            cylinder(d=TOL.bolt_hole_d(3), h=e.pad_t + 2, fn=FN_HOLE).translate(
                [e.hole_x, y, PAD_Z[0] - 1]
            )
        )
        board_holes.append(
            cylinder(d=TOL.nut_trap_ac(3), h=nut_t + 1, fn=6).translate([e.hole_x, y, PAD_Z[0] - 1])
        )
    return set_handles(pad - slots - board_holes, board=BOARD)


def x_endstop_mount() -> Solid:
    """Print orientation: pad bottom on the bed."""
    return x_endstop_mount_installed().translate([0, 0, -PAD_Z[0]])
