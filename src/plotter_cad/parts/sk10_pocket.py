"""SK10 pocket shared by the Y motor and idler mounts (STATUS.md T3.5, D26). Not printable.

The mount's foot is as thick as the SK10's base flange, so the SK10 sits in a cut-out of the
foot directly on the baseboard (the shaft height is unchanged). The cut-out has an end wall
against the SK10's outer face (the shaft end plane) and a side wall each side; it is open
toward the other SK10. The mount slides along the shaft axis onto an SK10 that is already
fixed, so the idler/pulley positions follow the shaft. The pocket walls are lower than the
SCS blocks' underside.

Left side frame (``params.YDrive``): x from the shaft, machine y, z = baseboard top.
"""

from enum import Enum
from typing import TYPE_CHECKING

from pythonscad import cube

from plotter_cad.geometry import EPS
from plotter_cad.hardware import Y_SHAFT
from plotter_cad.params import Y_AXIS, Y_DRIVE

if TYPE_CHECKING:
    from pythonscad import Solid


class PocketEnd(Enum):
    """Which end of the Y shafts a pocket is at."""

    FRONT = "front"
    REAR = "rear"


def sk10_pocket(end: PocketEnd, strip_x0: float) -> tuple[Solid, Solid]:
    """``(frame, cut)``: the frame around the SK10 plus a strip reaching outboard to
    ``strip_x0``, and the cut-out to subtract after joining it to the rest of the mount."""
    d = Y_DRIVE
    out = d.pocket_half + d.pocket_wall
    if end is PocketEnd.FRONT:
        y0, y1 = d.front_pocket_y
        cut_y = (Y_AXIS.shaft_y0, y1 + 1)
    else:
        y0, y1 = d.rear_pocket_y
        end_y = Y_AXIS.shaft_y0 + Y_SHAFT.length
        cut_y = (y0 - 1, end_y)
    frame = cube([out - strip_x0, y1 - y0, d.foot_t]).translate([strip_x0, y0, 0])
    cut = cube([2 * d.pocket_half, cut_y[1] - cut_y[0], d.foot_t + 2 * EPS]).translate(
        [-d.pocket_half, cut_y[0], -EPS]
    )
    return frame, cut
