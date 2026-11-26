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
    tooth_height: float = 0.75

    @property
    def pitch_line_from_back(self) -> float:
        """The pitch line lies 0.254 mm from the tooth roots, inside the belt back (≈ 0.38)."""
        return (self.thickness - self.tooth_height) - 0.254


GT2_SPEC = Gt2BeltSpec()


@dataclass(frozen=True)
class PulleySpec:
    """20T drive pulley (5 mm bore, grub screws)."""

    teeth: int = 20
    flange_dia: float = 16  #: ASSUMED
    length: float = 16  #: overall. ASSUMED
    hub_dia: float = 16  #: ASSUMED
    hub_length: float = 7  #: ASSUMED
    bore: float = 5

    @property
    def pitch_dia(self) -> float:
        """Pitch diameter (12.73)."""
        return self.teeth * GT2_SPEC.pitch / math.pi

    @property
    def outer_dia(self) -> float:
        """Tooth tips (≈ 12.22)."""
        return self.pitch_dia - 0.51

    @property
    def belt_z(self) -> float:
        """Belt center above the hub's motor-side face."""
        return self.hub_length + 1 + (self.length - self.hub_length - 2) / 2


@dataclass(frozen=True)
class IdlerSpec:
    """Toothed 20T idler with a bearing inside."""

    teeth: int = 20  #: ASSUMED
    bore: float = 5  #: ASSUMED
    flange_dia: float = 18  #: ASSUMED
    width: float = 8.5  #: overall, incl. flanges. ASSUMED

    @property
    def pitch_dia(self) -> float:
        """Pitch diameter."""
        return self.teeth * GT2_SPEC.pitch / math.pi


PULLEY_SPEC = PulleySpec()
IDLER_SPEC = IdlerSpec()


def gt2_pulley() -> Solid:
    """20T pulley. Origin: center of the hub's bottom face (motor side); axis +Z.

    The belt runs over z in ``[hub_length + 1, hub_length + 1 + belt width]``.
    """
    body = (
        cylinder(d=PULLEY_SPEC.hub_dia, h=PULLEY_SPEC.hub_length, fn=32)
        | cylinder(d=PULLEY_SPEC.flange_dia, h=1, fn=32).translate([0, 0, PULLEY_SPEC.hub_length])
        | cylinder(d=PULLEY_SPEC.outer_dia, h=PULLEY_SPEC.length - PULLEY_SPEC.hub_length, fn=40).translate(
            [0, 0, PULLEY_SPEC.hub_length]
        )
        | cylinder(d=PULLEY_SPEC.flange_dia, h=1, fn=32).translate([0, 0, PULLEY_SPEC.length - 1])
    )
    bore = cylinder(d=PULLEY_SPEC.bore, h=PULLEY_SPEC.length + 2, fn=20).translate([0, 0, -1])
    return (body - bore).color("Gold")


def gt2_idler() -> Solid:
    """Toothed idler. Origin: center, axis Z, symmetric about z = 0."""
    body = cylinder(d=IDLER_SPEC.pitch_dia - 0.5, h=IDLER_SPEC.width, center=True, fn=40)
    for sz in (-1, 1):
        body |= cylinder(d=IDLER_SPEC.flange_dia, h=1, center=True, fn=40).translate(
            [0, 0, sz * (IDLER_SPEC.width / 2 - 0.5)]
        )
    bore = cylinder(d=IDLER_SPEC.bore, h=IDLER_SPEC.width + 2, center=True, fn=20)
    return (body - bore).color("Gold")


def gt2_belt(length: float) -> Solid:
    """Straight belt run. Origin: start, running +X; width along Z, teeth at y = 0."""
    return cube([length, GT2_SPEC.thickness, GT2_SPEC.width]).color("#111")
