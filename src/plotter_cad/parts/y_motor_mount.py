"""Y motor mount (STATUS.md T3.5). Print ×1 left + ×1 right (mirror image).

Purpose: holds a Y NEMA17 on the baseboard behind the rear SK10, with its shaft pointing
outboard so the 20T pulley sits on the Y belt line (30 mm outboard of the shaft). The
plate carries the motor face; the foot (screwed to the baseboard) extends outboard,
where the screws stay accessible with the motor fitted.

  top view (left side)                      side view (looking along +x)
  belt ═◯pulley┃plate┃ motor body →         ┌─────────┐
        ═══════╋     ┃ (inboard)            │ ◯ motor │ plate
  ─ foot ──────┸─────┘                      └─────────┘ ← gussets at both ends
                                            ──── foot (4 × M4 wood screws)

Frame: left side frame (``params.YDrive``: x from the shaft, machine y, z = baseboard
top); the part is printed foot down in the same orientation. The right-hand part is the
mirror image (:func:`y_motor_mount`).

Hardware: 4 × M3×10 ISO 4762 (motor, from the pulley side); 20T GT2 pulley on the motor
(hub toward the motor, belt center on the belt line); 4 × M4 wood screws into the baseboard.
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; foot down; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import EPS, FN_HOLE, teardrop_x
from plotter_cad.hardware import NEMA17, metric
from plotter_cad.params import TOL, Y_AXIS, Y_DRIVE
from plotter_cad.parts.gantry_end_bracket import Side

if TYPE_CHECKING:
    from pythonscad import Solid

AXIS_Z = Y_AXIS.pulley_axis_z  #: motor axis height
SCREW_M = 4  #: wood screws into the baseboard
SCREW_INSET = 6  #: foot screws from the plate ends (y)


def y_motor_mount_installed() -> Solid:
    """The mount in the left side frame."""
    d = Y_DRIVE
    x0, x1 = d.motor_plate_x
    y0, y1 = d.motor_plate_y
    foot = cube([x1 - d.motor_foot_x0, y1 - y0, d.foot_t]).translate([d.motor_foot_x0, y0, 0])
    plate = cube([x1 - x0, y1 - y0, d.motor_top_z]).translate([x0, y0, 0])
    gussets = [
        hull(
            cube([d.gusset_len, d.gusset_t, EPS]).translate([x0 - d.gusset_len, y, d.foot_t - EPS]),
            cube([EPS, d.gusset_t, d.gusset_len]).translate([x0 - EPS, y, d.foot_t]),
        )
        for y in (y0, y1 - d.gusset_t)
    ]
    plate_cx = (x0 + x1) / 2
    boss = teardrop_x(NEMA17.boss_d + 0.4, d.motor_plate_t + 2).translate(
        [plate_cx, d.motor_y, AXIS_Z]
    )
    screws = [
        teardrop_x(TOL.bolt_hole_d(3), d.motor_plate_t + 2).translate(
            [
                plate_cx,
                d.motor_y + dy * NEMA17.hole_pitch / 2,
                AXIS_Z + dz * NEMA17.hole_pitch / 2,
            ]
        )
        for dy in (-1, 1)
        for dz in (-1, 1)
    ]
    foot_x = d.motor_foot_x0 + TOL.cbore_d(SCREW_M) / 2 + TOL.min_wall
    holes = []
    for y in (y0 + SCREW_INSET, y1 - SCREW_INSET):
        holes.append(
            cylinder(d=TOL.bolt_hole_d(SCREW_M), h=d.foot_t + 2, fn=FN_HOLE).translate(
                [foot_x, y, -1]
            )
        )
        holes.append(
            cylinder(d=TOL.cbore_d(SCREW_M), h=metric(SCREW_M).head_h + 1, fn=FN_HOLE).translate(
                [foot_x, y, d.foot_t - metric(SCREW_M).head_h]
            )
        )
    return (foot | plate | gussets) - boss - screws - holes


def y_motor_mount(side: Side = Side.LEFT) -> Solid:
    """The mount for one side, in print orientation (the right one is mirrored)."""
    mount = y_motor_mount_installed()
    return mount.mirror([1, 0, 0]) if side is Side.RIGHT else mount
