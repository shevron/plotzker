"""Zonestar ZRIB v5.8 controller board, out of its case. Dimensions in mm.

Measured by the user (T3.7): board 110 × 95 mm; 22 mm from the board's bottom to the top of
the driver heat sinks (the tallest parts); 4 × Ø3 mounting holes in the corners, 100 apart
along the 110 mm side and 80 apart along the 95 mm side. The 110 mm rear edge carries the
USB-B port and the DC input terminal (right) and the microSD slot (middle): it must stay
accessible. The PCB thickness and the layout of the tall parts are ASSUMED.

Model frame: origin at the center of the PCB's bottom face; ``x`` along the 110 mm (rear)
edge, ``y`` toward the rear edge, ``z`` up (the components are on the +z side).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class ZribSpec:
    """ZRIB board dimensions."""

    width: float = 110  #: along the rear edge
    depth: float = 95  #: front to rear
    pcb_t: float = 1.6  #: ASSUMED
    height: float = 22  #: bottom of the board to the top of the heat sinks (measured)
    hole_pitch: tuple[float, float] = (100, 80)  #: along the rear edge, front to rear
    hole_d: float = 3.0
    #: footprint of the tall parts (the driver heat sinks), centered. ASSUMED: the real
    #: layout is not measured; it only has to stay inside the 22 mm envelope
    tall_zone: tuple[float, float] = (90, 40)


ZRIB = ZribSpec()


def zrib() -> Solid:
    """The board: PCB with its mounting holes and a block standing for the tall parts."""
    z = ZRIB
    holes = [
        cylinder(d=z.hole_d, h=z.pcb_t + 2, fn=16).translate([sx * z.hole_pitch[0] / 2, sy * z.hole_pitch[1] / 2, -1])
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]
    pcb = cube([z.width, z.depth, z.pcb_t]).translate([-z.width / 2, -z.depth / 2, 0]) - holes
    tall = cube([*z.tall_zone, z.height - z.pcb_t]).translate([-z.tall_zone[0] / 2, -z.tall_zone[1] / 2, z.pcb_t])
    return pcb.color("DarkGreen") | tall.color("#444")
