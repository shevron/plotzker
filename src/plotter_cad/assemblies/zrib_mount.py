"""ZRIB under the baseboard: two hangers, two guard straps, the board and its screws (T3.7).

Mount frame of ``params.ZribMount`` (u along the board's 110 mm edge, v toward its rear edge,
z up with 0 at the baseboard underside). Shown with a piece of the baseboard. Not printable.
"""

from typing import TYPE_CHECKING

from pythonscad import cube

from plotter_cad.hardware import ZRIB, countersunk_screw, hex_nut, shcs, zrib
from plotter_cad.params import FRAME, TOL, WOOD_SCREW, ZMOUNT
from plotter_cad.parts.zrib_guard import zrib_guard
from plotter_cad.parts.zrib_hanger import zrib_hanger_mount

if TYPE_CHECKING:
    from pythonscad import Solid


def zrib_mount_assembly() -> list[Solid]:
    """Hangers, straps, board and fasteners in the mount frame (without the baseboard)."""
    m = ZMOUNT
    nut_t = TOL.nut_trap_h(3)
    post_v = abs(m.post_v)
    wood_v = abs(m.post_v + m.wood_screw_v)
    strap_v = abs(m.strap_screw_v)
    hanger = zrib_hanger_mount().color("SteelBlue")
    items: list[Solid] = [hanger, hanger.mirror([0, 1, 0])]
    # components down: flip the board about the v axis (y stays toward the rear edge)
    items.append(zrib().rotate([0, 180, 0]).translate([0, 0, m.board_z]))
    board_bottom = m.board_z - ZRIB.pcb_t
    for sv in (-1, 1):
        for sx in (-1, 1):
            u = sx * ZRIB.hole_pitch[0] / 2
            items.append(shcs(3, 12).rotate([180, 0, 0]).translate([u, sv * post_v, board_bottom]))
            items.append(hex_nut(3).translate([u, sv * post_v, -nut_t]))
            items.append(
                countersunk_screw(WOOD_SCREW.m, WOOD_SCREW.length, WOOD_SCREW.head_d)
                .rotate([180, 0, 0])
                .translate([sx * m.wood_screw_u, sv * wood_v, -WOOD_SCREW.boss_t])
            )
            items.append(
                shcs(3, m.strap_screw_len)
                .rotate([180, 0, 0])
                .translate([sx * m.strap_screw_u, sv * strap_v, m.strap_bottom_z])
            )
            items.append(
                hex_nut(3)
                .rotate([0, 0, 30])  # flats along u, as the slot is cut
                .translate([sx * m.strap_screw_u, sv * strap_v, m.strap_nut_z])
            )
        strap = zrib_guard().translate([0, sv * strap_v - m.leg_t / 2, m.strap_bottom_z])
        items.append(strap.color("Orange"))
    return items


def zrib_mount_fit_check() -> list[Solid]:
    """The mount on a piece of baseboard, shown upside down (the mount faces up)."""
    wood = cube([220, 200, FRAME.board_size[2]]).translate([-110, -100, 0]).color("BurlyWood", 0.5)
    return [item.rotate([180, 0, 0]) for item in (wood, *zrib_mount_assembly())]
