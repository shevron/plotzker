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
    pcb_thickness: float = 1.6  #: ASSUMED
    height: float = 22  #: bottom of the board to the top of the heat sinks (measured)
    hole_pitch: tuple[float, float] = (100, 80)  #: along the rear edge, front to rear
    hole_dia: float = 3.0
    #: footprint of the tall parts (the driver heat sinks), centered. ASSUMED: the real
    #: layout is not measured; it only has to stay inside the 22 mm envelope
    tall_zone: tuple[float, float] = (90, 40)


ZRIB_SPEC = ZribSpec()


def zrib() -> Solid:
    """The board: PCB with its mounting holes and a block standing for the tall parts."""
    holes = [
        cylinder(d=ZRIB_SPEC.hole_dia, h=ZRIB_SPEC.pcb_thickness + 2, fn=16).translate(
            [sx * ZRIB_SPEC.hole_pitch[0] / 2, sy * ZRIB_SPEC.hole_pitch[1] / 2, -1]
        )
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]
    pcb = (
        cube([ZRIB_SPEC.width, ZRIB_SPEC.depth, ZRIB_SPEC.pcb_thickness]).translate(
            [-ZRIB_SPEC.width / 2, -ZRIB_SPEC.depth / 2, 0]
        )
        - holes
    )
    tall = cube([*ZRIB_SPEC.tall_zone, ZRIB_SPEC.height - ZRIB_SPEC.pcb_thickness]).translate(
        [-ZRIB_SPEC.tall_zone[0] / 2, -ZRIB_SPEC.tall_zone[1] / 2, ZRIB_SPEC.pcb_thickness]
    )
    return pcb.color("DarkGreen") | tall.color("#444")
