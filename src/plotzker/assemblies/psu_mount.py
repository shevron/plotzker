"""The 24 V supply beside the baseboard's right edge: PSU, two brackets, the terminal hood with
the C14 inlet and the XT60, and their screws (T3.31, D38).

Built in the PSU frame (``hardware/psu.py``) and placed in the machine frame by
:func:`placed`: the PSU frame turns +90° about y (its x points down, its z out of the board's
edge) and moves to ``PSU_MOUNT.origin``. Not printable.
"""

from typing import TYPE_CHECKING

from cadder.handles import get_handle, get_handles
from cadder.hardware import countersunk_screw, hex_nut, shcs
from pythonscad import cube

from plotzker.hardware import PSU, c14_inlet, psu, xt60_female
from plotzker.params import FRAME, PSU_MOUNT, WOOD_SCREW
from plotzker.parts.psu_bracket import psu_bracket_installed
from plotzker.parts.psu_hood import psu_hood_installed

if TYPE_CHECKING:
    from pythonscad import Solid


def placed(item: Solid) -> Solid:
    """An item modeled in the PSU frame, in the machine frame."""
    return item.rotate([0, 90, 0]).translate(list(PSU_MOUNT.origin))


def brackets_local() -> list[Solid]:
    """Both brackets with their screws (PSU frame)."""
    m = PSU_MOUNT
    items: list[Solid] = []
    for y in PSU.hole_y:
        bracket = psu_bracket_installed().translate([0, y, 0])
        items.append(bracket.color("SteelBlue"))
        items += [
            shcs(PSU.hole_m, m.psu_screw_len).align(h) for h in get_handles(bracket, "psu_screws")
        ]
        items += [
            countersunk_screw(WOOD_SCREW.m, WOOD_SCREW.length, WOOD_SCREW.head_d).align(h)
            for h in get_handles(bracket, "wood_screws")
        ]
    return items


def hood_local() -> list[Solid]:
    """The hood with the inlet, the XT60 and the screws (PSU frame)."""
    m = PSU_MOUNT
    hood = psu_hood_installed()
    items: list[Solid] = [hood.color("Orange")]
    items.append(c14_inlet().align(get_handle(hood, "inlet")))
    items += [shcs(3, 10).align(h) for h in get_handles(hood, "inlet_screws")]
    items += [hex_nut(3).align(h) for h in get_handles(hood, "inlet_nuts")]
    items.append(xt60_female().align(get_handle(hood, "xt60")))
    items += [
        shcs(PSU.hole_m, m.hood_screw_len).align(h)
        for name in ("label_screws", "switch_screws")
        for h in get_handles(hood, name)
    ]
    return items


def psu_mount_local() -> list[Solid]:
    """Everything in the PSU frame."""
    return [psu(), *brackets_local(), *hood_local()]


def psu_mount_assembly() -> list[Solid]:
    """Everything in the machine frame."""
    return [placed(item) for item in psu_mount_local()]


def board_piece() -> Solid:
    """The corner of the baseboard the mount hangs from (machine frame)."""
    bx, _, t = FRAME.board_size
    y0 = PSU_MOUNT.terminal_y - PSU_MOUNT.depth - 20
    length = PSU.size[1] + PSU_MOUNT.depth + 40
    return cube([120, length, t]).translate([bx - 120, y0, -t]).color("BurlyWood", 0.5)


def psu_mount_fit_check() -> list[Solid]:
    """The mount on a piece of the baseboard."""
    return [board_piece(), *psu_mount_assembly()]
