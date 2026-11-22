"""GT2 belt, 20T pulleys and toothed idlers. Dimensions in mm.

The user has assorted common 3D-printer pulleys and idlers, so the design uses these
typical values and is adjusted at assembly if needed.
"""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class Gt2BeltSpec:
    """GT2 belt dimensions."""

    pitch: float = 2
    width: float = 6  #: confirmed: plenty on hand
    thickness: float = 1.38  #: total
    tooth_h: float = 0.75

    @property
    def pitch_line_from_back(self) -> float:
        """The pitch line lies 0.254 mm from the tooth roots, inside the belt back (≈ 0.38)."""
        return (self.thickness - self.tooth_h) - 0.254


GT2 = Gt2BeltSpec()


@dataclass(frozen=True)
class PulleySpec:
    """20T drive pulley (5 mm bore, grub screws)."""

    teeth: int = 20
    flange_d: float = 16  #: ASSUMED
    length: float = 16  #: overall. ASSUMED
    hub_d: float = 16  #: ASSUMED
    hub_len: float = 7  #: ASSUMED
    bore: float = 5

    @property
    def pd(self) -> float:
        """Pitch diameter (12.73)."""
        return self.teeth * GT2.pitch / math.pi

    @property
    def od(self) -> float:
        """Tooth tips (≈ 12.22)."""
        return self.pd - 0.51

    @property
    def belt_z(self) -> float:
        """Belt center above the hub's motor-side face."""
        return self.hub_len + 1 + (self.length - self.hub_len - 2) / 2


@dataclass(frozen=True)
class IdlerSpec:
    """Toothed 20T idler with a bearing inside."""

    teeth: int = 20  #: ASSUMED
    bore: float = 5  #: ASSUMED
    flange_d: float = 18  #: ASSUMED
    width: float = 8.5  #: overall, incl. flanges. ASSUMED

    @property
    def pd(self) -> float:
        """Pitch diameter."""
        return self.teeth * GT2.pitch / math.pi


PULLEY = PulleySpec()
IDLER = IdlerSpec()


def gt2_pulley() -> Solid:
    """20T pulley. Origin: center of the hub's bottom face (motor side); axis +Z.

    The belt runs over z in ``[hub_len + 1, hub_len + 1 + belt width]``.
    """
    p = PULLEY
    body = (
        cylinder(d=p.hub_d, h=p.hub_len, fn=32)
        | cylinder(d=p.flange_d, h=1, fn=32).translate([0, 0, p.hub_len])
        | cylinder(d=p.od, h=p.length - p.hub_len, fn=40).translate([0, 0, p.hub_len])
        | cylinder(d=p.flange_d, h=1, fn=32).translate([0, 0, p.length - 1])
    )
    bore = cylinder(d=p.bore, h=p.length + 2, fn=20).translate([0, 0, -1])
    return (body - bore).color("Gold")


def gt2_idler() -> Solid:
    """Toothed idler. Origin: center, axis Z, symmetric about z = 0."""
    i = IDLER
    body = cylinder(d=i.pd - 0.5, h=i.width, center=True, fn=40)
    for sz in (-1, 1):
        body |= cylinder(d=i.flange_d, h=1, center=True, fn=40).translate(
            [0, 0, sz * (i.width / 2 - 0.5)]
        )
    bore = cylinder(d=i.bore, h=i.width + 2, center=True, fn=20)
    return (body - bore).color("Gold")


def gt2_belt(length: float) -> Solid:
    """Straight belt run. Origin: start, running +X; width along Z, teeth at y = 0."""
    return cube([length, GT2.thickness, GT2.width]).color("#111")
