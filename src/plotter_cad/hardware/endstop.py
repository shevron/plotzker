"""Creality-type mechanical endstop board (user's, from a Creality printer). Dimensions in mm.

Measured by the user: board 20 wide × 19 long; 27 long including the open switch
lever; 2 mounting holes 15 apart; ~12 thick including the connector.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class EndstopSpec:
    """Mechanical endstop switch dimensions."""

    pcb: tuple[float, float, float] = (19, 20, 1.6)  #: L (lever direction) × W × T; T ASSUMED
    len_lever: float = 27  #: PCB + open lever (measured)
    height: float = 12  #: PCB bottom to top of the connector (measured)
    hole_pitch: float = 15  #: measured
    hole_m: float = 3  #: probably M3 (user unsure). ASSUMED
    hole_d: float = 3.2  #: ASSUMED
    hole_axis: str = "width"  #: holes lie across the 20 mm width. ASSUMED
    switch: tuple[float, float, float] = (12.8, 5.8, 6.5)  #: KW12-type body. ASSUMED
    travel_to_trip: float = 1.5  #: lever travel to click. ASSUMED

    @property
    def hole_x(self) -> float:
        """Hole line from the board center, on the side away from the switch. ASSUMED"""
        return -self.pcb[0] / 2 + 4


ENDSTOP = EndstopSpec()


def endstop() -> Solid:
    """Endstop board.

    Origin: PCB bottom face, center between the mounting holes. Switch on top at the
    +X edge; the lever reaches ``len_lever`` along +X from the board's -X edge;
    connector on top at the -X side.
    """
    e = ENDSTOP
    length, width, t = e.pcb
    holes = [
        cylinder(d=e.hole_d, h=t + 2, fn=16).translate([e.hole_x, sy * e.hole_pitch / 2, -1])
        for sy in (-1, 1)
    ]
    pcb = (cube([length, width, t]).translate([-length / 2, -width / 2, 0]) - holes).color("Red")
    switch = (
        cube(list(e.switch))
        .translate([length / 2 - e.switch[0], -e.switch[1] / 2, t])
        .color("Black")
    )
    lever = (
        cube([e.len_lever - length + 3, 4, 0.4])
        .rotate([0, -6, 0])
        .translate([length / 2 - 3, -2, t + e.switch[2] - 0.5])
        .color("Silver")
    )
    connector = cube([6, 10, e.height - t]).translate([-length / 2 + 1, -5, t]).color("White")
    return (pcb | switch | lever | connector).translate([-e.hole_x, 0, 0])
