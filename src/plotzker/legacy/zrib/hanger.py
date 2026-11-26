"""ZRIB hanger: carries the controller under the baseboard (STATUS.md T3.7, D30). Print ×2.

Purpose: one of two identical hangers (they are mirror images in the machine, and print
the same) screwed to the underside of the baseboard, one along each long side of the
ZRIB. A rail with two posts carries the board at its mounting holes (components pointing
down, heat sinks in free air); two legs reach down past the board's ends to take the guard
strap. The board's 110 mm rear edge (USB-B, DC terminal, microSD) stays free.

  front view of one hanger (along v), baseboard on top

  ═══════════════════════════════════════   baseboard underside, z = 0
   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒    rail ◎ wood screws (u = ±59) ◎ post nuts (u = ±50)
   ▒▒        ┃post            post┃        ▒▒    legs (one M3 nut slot each, for the strap)
   ▒▒        ░░░░░ ZRIB ░░░░░░░░░░         ▒▒
   ▒▒                                        ▒▒

Frame: ``params.ZribMount`` mount frame (u along the board's 110 mm edge, v toward the rear
edge, z up with 0 at the baseboard underside, parts at negative z); this module builds the
hanger on the front (negative v) side. :func:`zrib_hanger_mount` returns it there;
:func:`zrib_hanger` in print orientation (outer face down).

Hardware per hanger:
  2 × M3×12 ISO 4762 + 2 × M3 nuts (pressed into the rail's top face; the plywood closes them)
  2 × 4×25 countersunk wood screws into the plywood (boss thickness keeps them 2 mm short of
      the top face)
  2 × M3 nuts in the leg slots + the strap's screws (see guard.py)

Print: PETG; 0.2 mm layers; 4 perimeters; 40 % infill; outer face (v) down; no supports
(the holes along z are teardrops pointing up; the nut slots open to the bed face).
"""

from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE, teardrop
from cadder.handles import handle, set_handles
from cadder.printing import nut_slot
from cadder.types import Matrix
from pythonscad import cube, cylinder, linear_extrude

from plotzker.legacy.zrib.board import ZRIB_SPEC
from plotzker.legacy.zrib.params import ZMOUNT
from plotzker.params import TOL, WOOD_SCREW

if TYPE_CHECKING:
    from pythonscad import Solid


def _handles() -> dict[str, Matrix | list[Matrix]]:
    """Handles of the negative-v hanger for the hardware that meets it (mount frame)."""
    board_bottom = ZMOUNT.board_z - ZRIB_SPEC.pcb_thickness
    sides = (-1, 1)
    return {
        "board": handle([0, 0, ZMOUNT.board_z], [0, 180, 0]),
        #: M3×12 up through the post and rail, head under the board's solder side
        "board_screws": [
            handle([sx * ZRIB_SPEC.hole_pitch[0] / 2, ZMOUNT.post_v, board_bottom], [180, 0, 0]) for sx in sides
        ],
        "post_nuts": [
            handle([sx * ZRIB_SPEC.hole_pitch[0] / 2, ZMOUNT.post_v, -TOL.nut_trap_height(3)]) for sx in sides
        ],
        "wood_screws": [
            handle(
                [sx * ZMOUNT.wood_screw_u, ZMOUNT.post_v + ZMOUNT.wood_screw_v, -WOOD_SCREW.boss_thickness],
                [180, 0, 0],
            )
            for sx in sides
        ],
        "strap_screws": [
            handle([sx * ZMOUNT.strap_screw_u, ZMOUNT.strap_screw_v, ZMOUNT.strap_bottom_z], [180, 0, 0])
            for sx in sides
        ],
        #: corners along u (a flat leads into the slot, CODING_STANDARDS.md §5)
        "strap_nuts": [handle([sx * ZMOUNT.strap_screw_u, ZMOUNT.strap_screw_v, ZMOUNT.strap_nut_z]) for sx in sides],
        "strap": handle([0, ZMOUNT.strap_screw_v - ZMOUNT.leg_thickness / 2, ZMOUNT.strap_bottom_z]),
    }


def _box(u0: float, u1: float, v0: float, v1: float, z0: float, z1: float) -> Solid:
    """Box between the given mount-frame extents."""
    return cube([u1 - u0, v1 - v0, z1 - z0]).translate([u0, v0, z0])


def _hole_z(dia: float, u: float, v: float, z0: float, z1: float) -> Solid:
    """Hole along z: a teardrop pointing +v (up in the print)."""
    return linear_extrude(teardrop(dia), height=z1 - z0).translate([u, v, z0])


def zrib_hanger_mount() -> Solid:
    """The hanger on the negative-v side of the board, in the mount frame."""
    v0, v1 = ZMOUNT.plate_v
    leg_out = ZMOUNT.leg_u[1]
    rail = _box(-leg_out, leg_out, v0, v1, -ZMOUNT.rail_thickness, 0)
    body = rail
    for sign_x in (-1, 1):
        u_in, u_out = sorted((sign_x * ZMOUNT.leg_u[0], sign_x * ZMOUNT.leg_u[1]))
        body = body | _box(u_in, u_out, v0, v0 + ZMOUNT.leg_thickness, ZMOUNT.strap_top_z, 0)
        post = cylinder(d=ZMOUNT.post_dia, h=ZMOUNT.post_height + 0.01, fn=FN_HOLE).translate(
            [sign_x * ZRIB_SPEC.hole_pitch[0] / 2, ZMOUNT.post_v, -ZMOUNT.rail_thickness - ZMOUNT.post_height]
        )
        boss = cylinder(d=ZMOUNT.boss_dia, h=WOOD_SCREW.boss_thickness, fn=FN_HOLE).translate(
            [sign_x * ZMOUNT.wood_screw_u, ZMOUNT.post_v + ZMOUNT.wood_screw_v, -WOOD_SCREW.boss_thickness]
        )
        body = body | post | boss

    nut_thickness, nut_across_corners = TOL.nut_trap_height(3), TOL.nut_trap_across_corners(3)
    for sign_x in (-1, 1):
        u = sign_x * ZRIB_SPEC.hole_pitch[0] / 2
        body = body - _hole_z(
            TOL.bolt_hole_dia(3), u, ZMOUNT.post_v, -ZMOUNT.rail_thickness - ZMOUNT.post_height - 1, 1
        )  # board screw, through post and rail
        body = body - cylinder(d=nut_across_corners, h=nut_thickness + 1, fn=6).translate(
            [u, ZMOUNT.post_v, -nut_thickness]
        )
        screw_u = sign_x * ZMOUNT.wood_screw_u
        screw_v = ZMOUNT.post_v + ZMOUNT.wood_screw_v
        body = body - _hole_z(WOOD_SCREW.hole_dia, screw_u, screw_v, -WOOD_SCREW.boss_thickness - 1, 1)
        # countersink (90°), wide end on the boss's underside
        body = body - cylinder(
            d1=WOOD_SCREW.sink_dia + 2, d2=WOOD_SCREW.hole_dia, h=WOOD_SCREW.sink_height + 1, fn=FN_HOLE
        ).translate([screw_u, screw_v, -WOOD_SCREW.boss_thickness - 1])
        # strap screw: hole up the leg, nut slot pressed in from the outer face
        screw_u = sign_x * ZMOUNT.strap_screw_u
        body = body - _hole_z(
            TOL.bolt_hole_dia(3),
            screw_u,
            ZMOUNT.strap_screw_v,
            ZMOUNT.strap_top_z - 1,
            ZMOUNT.strap_nut_z + nut_thickness + 5,
        )
        body = body - nut_slot(3, ZMOUNT.strap_screw_v - v0 + 1, "z", "-y", tol=TOL).translate(
            [screw_u, ZMOUNT.strap_screw_v, ZMOUNT.strap_nut_z + nut_thickness / 2]
        )
    return set_handles(body, **_handles())


def zrib_hanger() -> Solid:
    """The hanger in print orientation: outer face (v) down."""
    v0 = ZMOUNT.plate_v[0]
    return zrib_hanger_mount().rotate([90, 0, 0]).translate([0, 0, -v0])
