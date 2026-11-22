"""Hex-profile pocket for a nut pressed in sideways (STATUS.md T3.12).

A nut that is pressed into a slot from an edge sits **flat-first** (a flat faces the pressing
direction, so a thumb pushes straight onto it) and must not turn when the bolt is tightened.
A plain rectangular slot wide enough for the corners lets it spin; this pocket instead follows
the hex outline at the bottom (flat floor, two 60° sloped sides up to the corners), which holds
the nut like an axial hex pocket, and continues with straight walls up to the entrance.
It needs no supports: the sloped sides are 30° from vertical.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from plotzker.geometry import EPS, cos_deg
from plotzker.hardware import metric
from plotzker.params import TOL

if TYPE_CHECKING:
    from pythonscad import Solid

#: Euler rotations from the canonical frame (bolt axis y, entrance toward +z) to
#: ``(bolt axis, entrance direction)``.
_ROTATIONS: dict[tuple[str, str], tuple[float, float, float]] = {
    ("y", "+z"): (0, 0, 0),
    ("y", "-z"): (0, 180, 0),
    ("x", "+z"): (0, 0, -90),
    ("x", "-z"): (0, 180, -90),
    ("z", "-y"): (90, 0, 0),
    ("z", "+y"): (90, 0, 180),
    ("z", "+x"): (90, 0, 90),
    ("z", "-x"): (90, 0, -90),
}


def nut_slot(m: float, reach: float, axis: str, entrance: str, extra_t: float = 0) -> Solid:
    """Pocket for an M``m`` nut, centered on the nut's center.

    ``axis``: the bolt's axis (``"x"``, ``"y"`` or ``"z"``); ``entrance``: the direction the
    nut is pressed in from, as a signed axis (``"+z"``, ``"-x"``...): the pocket's floor lies
    below the nut and the pocket runs out to ``reach`` mm from the nut's center toward the
    entrance. Combinations not in ``_ROTATIONS`` are added when needed. ``extra_t`` makes the
    pocket that much thicker (a long pocket whose print orientation makes it come out tight).
    """
    af = metric(m).nut_af + TOL.nut_slot  # across flats (the print comes out ~0.1 narrow)
    ac = af / cos_deg(30)
    t = TOL.nut_trap_h(m) + extra_t
    hexagon = cylinder(d=ac, h=t, fn=6).rotate([90, 0, 0]).translate([0, t / 2, 0])
    walls = cube([ac, t, reach + EPS]).translate([-ac / 2, -t / 2, -EPS])
    return (hexagon | walls).rotate(list(_ROTATIONS[axis, entrance]))
