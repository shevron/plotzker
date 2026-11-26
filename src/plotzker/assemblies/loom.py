"""Y loom (T3.8, D32): the loom as a chain of capsules, and the rail segments beside the belt.

The loom runs from the anchor on the right bracket, out and down to the baseboard, along the
moving leg to the U fold, back along the static leg and through the baseboard hole to the controller.
Machine frame (``params``). Not printable.
"""

import itertools
import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pythonscad import hull, sphere

from plotzker.params import LOOM, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid

Point = list[float]

BEND_STEP_DEG = 15
#: How far under the baseboard the loom model reaches (it leaves through the hole)
UNDER_BOARD = 30


def _arc(
    center: tuple[float, float, float],
    axes: tuple[Sequence[float], Sequence[float]],
    start_deg: float,
    end_deg: float,
) -> list[Point]:
    """Points of an arc of radius ``LOOM.bend_radius`` around ``center``, in the plane spanned by
    the unit vectors ``axes`` (angle measured from the first toward the second)."""
    u, v = axes
    point_count = max(2, round(abs(end_deg - start_deg) / BEND_STEP_DEG) + 1)
    points = []
    for i in range(point_count):
        angle = math.radians(start_deg + (end_deg - start_deg) * i / (point_count - 1))
        points.append(
            [center[k] + LOOM.bend_radius * (math.cos(angle) * u[k] + math.sin(angle) * v[k]) for k in range(3)]
        )
    return points


def y_loom_path(gantry_y: float) -> list[Point]:
    """Axis of the loom for the gantry at ``gantry_y``, from the anchor groove to the hole."""
    radius, z0 = LOOM.bend_radius, LOOM.lying_z
    moving_x, static_x = LOOM.moving_x, LOOM.hole_x
    exit_y = gantry_y + LOOM.exit_dy  #: the anchor's groove axis (y)
    shaft_x = Y_AXIS.shaft_x[1]
    groove_x0 = shaft_x - LOOM.anchor_x[1]  #: inboard end of the groove (right bracket: mirrored)
    groove_z = Y_AXIS.scs_top_z + LOOM.groove_z
    fold_y = LOOM.fold_y(gantry_y)
    path: list[Point] = [[groove_x0, exit_y, groove_z], [moving_x - radius, exit_y, groove_z]]
    path += _arc((moving_x - radius, exit_y, groove_z - radius), ((0, 0, 1), (1, 0, 0)), 0, 90)  # out, then down
    path += _arc((moving_x, exit_y + radius, z0 + radius), ((0, -1, 0), (0, 0, -1)), 0, 90)  # down, then back (+y)
    path.append([moving_x, fold_y, z0])
    path += _arc(((moving_x + static_x) / 2, fold_y, z0), ((-1, 0, 0), (0, 1, 0)), 0, 180)  # U fold
    path += [[static_x, LOOM.hole_y, z0], [static_x, LOOM.hole_y, -UNDER_BOARD]]
    return path


def y_loom(gantry_y: float) -> list[Solid]:
    """The loom as capsules along :func:`y_loom_path`."""
    path = y_loom_path(gantry_y)
    ball = sphere(d=LOOM.dia, fn=12)
    return [hull(ball.translate(a), ball.translate(b)).color("#333") for a, b in itertools.pairwise(path)]


def rails() -> list[Solid]:
    """The six inner rail segments on the baseboard, wall face 42 mm from the shaft."""
    from plotzker.parts.loom_rail import loom_rail

    return [loom_rail().translate([LOOM.rail_x, y0, 0]).color("SteelBlue") for y0 in LOOM.rail_starts]
