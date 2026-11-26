"""ZRIB under the baseboard: two hangers, two guard straps, the board and its screws (T3.7).

Mount frame of ``params.ZribMount`` (u along the board's 110 mm edge, v toward its rear edge,
z up with 0 at the baseboard underside). Shown with a piece of the baseboard. Not printable.
"""

from typing import TYPE_CHECKING

from cadder.handles import get_handle, get_handles
from cadder.hardware import countersunk_screw, hex_nut, shcs
from pythonscad import cube

from plotzker.hardware import zrib
from plotzker.params import FRAME, WOOD_SCREW, ZMOUNT
from plotzker.parts.zrib_guard import zrib_guard
from plotzker.parts.zrib_hanger import zrib_hanger_mount

if TYPE_CHECKING:
    from pythonscad import Solid


def zrib_mount_assembly() -> list[Solid]:
    """Hangers, straps, board and fasteners in the mount frame (without the baseboard)."""
    hanger = zrib_hanger_mount()
    items: list[Solid] = []
    for side in (hanger, hanger.mirror([0, 1, 0])):
        items.append(side.color("SteelBlue"))
        items += [shcs(3, 12).align(h) for h in get_handles(side, "board_screws")]
        items += [hex_nut(3).align(h) for h in get_handles(side, "post_nuts")]
        items += [
            countersunk_screw(WOOD_SCREW.dia, WOOD_SCREW.length, WOOD_SCREW.head_dia).align(h)
            for h in get_handles(side, "wood_screws")
        ]
        items += [shcs(3, ZMOUNT.strap_screw_length).align(h) for h in get_handles(side, "strap_screws")]
        items += [hex_nut(3).align(h) for h in get_handles(side, "strap_nuts")]
        items.append(zrib_guard().align(get_handle(side, "strap")).color("Orange"))
    # components down: flip the board about the v axis (y stays toward the rear edge)
    items.append(zrib().align(get_handle(hanger, "board")))
    return items


def zrib_mount_fit_check() -> list[Solid]:
    """The mount on a piece of baseboard, shown upside down (the mount faces up)."""
    wood = cube([220, 200, FRAME.board_size[2]]).translate([-110, -100, 0]).color("BurlyWood", 0.5)
    return [item.rotate([180, 0, 0]) for item in (wood, *zrib_mount_assembly())]
