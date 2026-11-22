"""Every vendor-part model from :mod:`plotzker.hardware`, laid out for a visual check.

Not printable.
"""

from typing import TYPE_CHECKING

from cadder.hardware import (
    B608,
    B623,
    B625,
    IDLER,
    LM6UU,
    LM8UU,
    VWHEEL,
    bearing,
    gt2_belt,
    gt2_idler,
    gt2_pulley,
    hex_nut,
    nema17,
    scs10uu,
    servo_ft90m,
    shcs,
    sk10,
    vslot_x,
    vwheel,
    washer,
)

from plotzker.hardware import endstop, y_shaft

if TYPE_CHECKING:
    from pythonscad import Solid

GRID = 60  #: spacing of the first row


def hardware_gallery() -> list[Solid]:
    """All vendor-part models laid out in rows for a visual check."""
    first_row = [
        sk10(),
        scs10uu(),
        nema17(),
        gt2_pulley(),
        gt2_idler().translate([0, 0, IDLER.width / 2]),
        vwheel().translate([0, 0, VWHEEL.od / 2]),
        servo_ft90m(),
        endstop(),
    ]
    items = [model.translate([i * GRID, 0, 0]) for i, model in enumerate(first_row)]

    profiles = [
        vslot_x(80, (1, 2)),  # 4020 upright
        vslot_x(80, (1, 1)).translate([100, 0, 0]),  # 2020
        vslot_x(80, (2, 1)).translate([200, 0, 0]),  # 2040 lying flat
        y_shaft(80).translate([300, 0, 0]),
        gt2_belt(80).translate([340, 0, 0]),
    ]
    items += [p.translate([0, 60, 0]) for p in profiles]

    small = []
    for i, m in enumerate((2.5, 3, 4, 5)):
        small += [
            shcs(m, 12).translate([i * 20, 0, 12]),
            hex_nut(m).translate([i * 20, 15, 0]),
            washer(m).translate([i * 20, 30, 0]),
        ]
    for x, b in ((100, B608), (130, B625), (155, B623), (180, LM8UU), (205, LM6UU)):
        small.append(bearing(b).translate([x, 0, 0]))
    items += [s.translate([0, -60, 0]) for s in small]
    return items
