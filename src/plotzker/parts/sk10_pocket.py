"""SK10 pocket shared by the Y motor and idler mounts (STATUS.md T3.5, D26). Not printable.

The mount's foot is as thick as the SK10's base flange, so the SK10 sits in a cut-out of the
foot directly on the baseboard (the shaft height is unchanged). The cut-out is a corner: an
end wall (a short finger, ``YDrive.pocket_end_len``, so it isn't fragile) against the SK10's
outer face (the shaft end plane) and an outboard side wall against its outboard edge. It is
open toward the other SK10 and toward the inboard side, so the SK10's width and chamfer
tolerances don't matter: the mount slides onto an SK10 that is already fixed and is pushed
into the corner, so the idler/pulley positions follow the shaft. The walls are lower than the
SCS blocks' underside.

Left side frame (``params.YDrive``): x from the shaft, machine y, z = baseboard top.
"""

from enum import Enum
from typing import TYPE_CHECKING

from cadder.geometry import EPS
from pythonscad import cube

from plotzker.hardware import Y_SHAFT
from plotzker.params import Y_AXIS, Y_DRIVE

if TYPE_CHECKING:
    from pythonscad import Solid


class PocketEnd(Enum):
    """Which end of the Y shafts a pocket is at."""

    FRONT = "front"
    REAR = "rear"


def sk10_pocket(end: PocketEnd, strip_x0: float) -> tuple[Solid, Solid]:
    """``(frame, cut)``: the frame around the SK10 plus a strip reaching outboard to
    ``strip_x0``, and the cut-out to subtract after joining it to the rest of the mount."""
    if end is PocketEnd.FRONT:
        y0, y1 = Y_DRIVE.front_pocket_y
        cut_y = (Y_AXIS.shaft_y0, y1 + 1)
    else:
        y0, y1 = Y_DRIVE.rear_pocket_y
        end_y = Y_AXIS.shaft_y0 + Y_SHAFT.length
        cut_y = (y0 - 1, end_y)
    # the end wall reaches part way across the SK10's face; the rest of the pocket is open
    frame_x1 = -Y_DRIVE.pocket_half + Y_DRIVE.pocket_end_len
    frame = cube([frame_x1 - strip_x0, y1 - y0, Y_DRIVE.foot_t]).translate([strip_x0, y0, 0])
    cut = cube([2 * Y_DRIVE.pocket_half + 1, cut_y[1] - cut_y[0], Y_DRIVE.foot_t + 2 * EPS]).translate(
        [-Y_DRIVE.pocket_half, cut_y[0], -EPS]
    )
    return frame, cut
