"""X− endstop switch mount (README §8 T3.4). Print ×1.

Purpose: holds the X endstop board (Creality type) upright behind the beam at the
left end, switch facing +x, lever pointing −y. At the carriage's left end of travel
the head of the carriage's trigger screw presses the lever toward −x. Sits on top of
the X idler mount; slots give ±4 mm of x adjustment on top of the trigger screw's.

  top view                          front view (from +x)
  ┌pad (2 × M3 slots)┐──arm──┐      ┌─plate─┐
  └──────────────────┘       ║←board│ ▫  ▫  │ ← board holes
                             ║ lever│  ┌──┐ │
                             ╚═══►  │  └──┘ │ switch

Frame: LEFT bracket-local (``params.XDrive``), z = 0 on the SCS top face
(:func:`x_endstop_mount_installed`). Board position and hole layout follow
``hardware.ENDSTOP`` (partly ASSUMED: holes across the width, 4 mm from the far end;
connector on the switch side).

Hardware: 2 × M3×10 ISO 4762 + washers into the idler mount's inserts;
2 × M3×8 (or the board's own screws) self-tapping into the Ø2.6 pilot holes.
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; plate front face down;
no supports.
"""

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import EPS, FN_HOLE
from plotter_cad.hardware import ENDSTOP
from plotter_cad.params import CARRIAGE, TOL, X_DRIVE, X_ENDSTOP, Y_AXIS

TRIG_Z = CARRIAGE.trig_z - Y_AXIS.scs_top_z  #: trigger screw axis, local z
TOP_Z = X_DRIVE.idler_top_z - Y_AXIS.scs_top_z  #: idler plate top, local z
PLATE_YC = X_DRIVE.plate_y0 + X_DRIVE.idler_plate_t / 2
PLATE_X = (X_ENDSTOP.plate_front_x - X_ENDSTOP.plate_t, X_ENDSTOP.plate_front_x)
PLATE_Y = (X_ENDSTOP.board_y[0] - 2, X_ENDSTOP.board_y[1] + 2)
PLATE_Z = (TRIG_Z - ENDSTOP.pcb[1] / 2 - 2, TRIG_Z + ENDSTOP.pcb[1] / 2 + 2)
ARM_Y = (X_DRIVE.plate_y0, X_DRIVE.plate_y0 + X_DRIVE.idler_plate_t)
ARM_T = 6
PAD_X0 = -26
PILOT_D = 2.6  #: M3 self-tapping into the board's holes
#: Board hole center (y): holes across the board width, at the far end
BOARD_HOLE_Y = X_ENDSTOP.board_y[1] - ENDSTOP.pcb[0] / 2 - ENDSTOP.hole_x


def x_endstop_mount_installed():
    """The mount in the left bracket-local frame."""
    e = X_ENDSTOP
    plate = cube([e.plate_t, PLATE_Y[1] - PLATE_Y[0], PLATE_Z[1] - PLATE_Z[0]]).translate(
        [PLATE_X[0], PLATE_Y[0], PLATE_Z[0]]
    )
    arm = cube([PLATE_X[0] - PAD_X0 + EPS, ARM_Y[1] - ARM_Y[0], ARM_T]).translate(
        [PAD_X0, ARM_Y[0], TOP_Z]
    )
    # pad slots (±pad_slot along x)
    slots = [
        hull(
            *(
                cylinder(d=TOL.bolt_hole_d(3), h=ARM_T + 2, fn=FN_HOLE).translate(
                    [x + dx, PLATE_YC, TOP_Z - 1]
                )
                for dx in (-e.pad_slot, e.pad_slot)
            )
        )
        for x in X_DRIVE.endstop_insert_x
    ]
    pilots = [
        cylinder(d=PILOT_D, h=e.plate_t + 5, fn=FN_HOLE)
        .rotate([0, -90, 0])
        .translate([PLATE_X[1] + 1, BOARD_HOLE_Y, TRIG_Z + sz * ENDSTOP.hole_pitch / 2])
        for sz in (-1, 1)
    ]
    return (plate | arm) - slots - pilots


def x_endstop_mount():
    """Print orientation: plate front face (+x) down, arm pointing up."""
    return x_endstop_mount_installed().rotate([0, 90, 0]).translate([0, 0, X_ENDSTOP.plate_front_x])
