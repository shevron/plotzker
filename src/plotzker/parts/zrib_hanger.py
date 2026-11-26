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
  2 × M3 nuts in the leg slots + the strap's screws (see zrib_guard.py)

Print: PETG; 0.2 mm layers; 4 perimeters; 40 % infill; outer face (v) down; no supports
(the holes along z are teardrops pointing up; the nut slots open to the bed face).
"""

from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE, teardrop
from cadder.handles import handle, set_handles
from cadder.printing import nut_slot
from cadder.types import Matrix
from pythonscad import cube, cylinder, linear_extrude

from plotzker.hardware import ZRIB
from plotzker.params import TOL, WOOD_SCREW, ZMOUNT

if TYPE_CHECKING:
    from pythonscad import Solid


def _handles() -> dict[str, Matrix | list[Matrix]]:
    """Handles of the negative-v hanger for the hardware that meets it (mount frame)."""
    m = ZMOUNT
    board_bottom = m.board_z - ZRIB.pcb_t
    sides = (-1, 1)
    return {
        "board": handle([0, 0, m.board_z], [0, 180, 0]),
        #: M3×12 up through the post and rail, head under the board's solder side
        "board_screws": [handle([sx * ZRIB.hole_pitch[0] / 2, m.post_v, board_bottom], [180, 0, 0]) for sx in sides],
        "post_nuts": [handle([sx * ZRIB.hole_pitch[0] / 2, m.post_v, -TOL.nut_trap_h(3)]) for sx in sides],
        "wood_screws": [
            handle([sx * m.wood_screw_u, m.post_v + m.wood_screw_v, -WOOD_SCREW.boss_t], [180, 0, 0]) for sx in sides
        ],
        "strap_screws": [
            handle([sx * m.strap_screw_u, m.strap_screw_v, m.strap_bottom_z], [180, 0, 0]) for sx in sides
        ],
        #: corners along u (a flat leads into the slot, README §7.4)
        "strap_nuts": [handle([sx * m.strap_screw_u, m.strap_screw_v, m.strap_nut_z]) for sx in sides],
        "strap": handle([0, m.strap_screw_v - m.leg_t / 2, m.strap_bottom_z]),
    }


def _box(u0: float, u1: float, v0: float, v1: float, z0: float, z1: float) -> Solid:
    """Box between the given mount-frame extents."""
    return cube([u1 - u0, v1 - v0, z1 - z0]).translate([u0, v0, z0])


def _hole_z(d: float, u: float, v: float, z0: float, z1: float) -> Solid:
    """Hole along z: a teardrop pointing +v (up in the print)."""
    return linear_extrude(teardrop(d), height=z1 - z0).translate([u, v, z0])


def zrib_hanger_mount() -> Solid:
    """The hanger on the negative-v side of the board, in the mount frame."""
    m = ZMOUNT
    v0, v1 = m.plate_v
    leg_out = m.leg_u[1]
    rail = _box(-leg_out, leg_out, v0, v1, -m.rail_t, 0)
    body = rail
    for sx in (-1, 1):
        u_in, u_out = sorted((sx * m.leg_u[0], sx * m.leg_u[1]))
        body = body | _box(u_in, u_out, v0, v0 + m.leg_t, m.strap_top_z, 0)
        post = cylinder(d=m.post_d, h=m.post_h + 0.01, fn=FN_HOLE).translate(
            [sx * ZRIB.hole_pitch[0] / 2, m.post_v, -m.rail_t - m.post_h]
        )
        boss = cylinder(d=m.boss_d, h=WOOD_SCREW.boss_t, fn=FN_HOLE).translate(
            [sx * m.wood_screw_u, m.post_v + m.wood_screw_v, -WOOD_SCREW.boss_t]
        )
        body = body | post | boss

    nut_t, nut_ac = TOL.nut_trap_h(3), TOL.nut_trap_ac(3)
    for sx in (-1, 1):
        u = sx * ZRIB.hole_pitch[0] / 2
        body = body - _hole_z(
            TOL.bolt_hole_d(3), u, m.post_v, -m.rail_t - m.post_h - 1, 1
        )  # board screw, through post and rail
        body = body - cylinder(d=nut_ac, h=nut_t + 1, fn=6).translate([u, m.post_v, -nut_t])
        us = sx * m.wood_screw_u
        vs = m.post_v + m.wood_screw_v
        body = body - _hole_z(WOOD_SCREW.hole_d, us, vs, -WOOD_SCREW.boss_t - 1, 1)
        # countersink (90°), wide end on the boss's underside
        body = body - cylinder(
            d1=WOOD_SCREW.sink_d + 2, d2=WOOD_SCREW.hole_d, h=WOOD_SCREW.sink_h + 1, fn=FN_HOLE
        ).translate([us, vs, -WOOD_SCREW.boss_t - 1])
        # strap screw: hole up the leg, nut slot pressed in from the outer face
        us = sx * m.strap_screw_u
        body = body - _hole_z(TOL.bolt_hole_d(3), us, m.strap_screw_v, m.strap_top_z - 1, m.strap_nut_z + nut_t + 5)
        body = body - nut_slot(3, m.strap_screw_v - v0 + 1, "z", "-y", tol=TOL).translate(
            [us, m.strap_screw_v, m.strap_nut_z + nut_t / 2]
        )
    return set_handles(body, **_handles())


def zrib_hanger() -> Solid:
    """The hanger in print orientation: outer face (v) down."""
    v0 = ZMOUNT.plate_v[0]
    return zrib_hanger_mount().rotate([90, 0, 0]).translate([0, 0, -v0])
