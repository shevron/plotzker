"""Loom rail segment (STATUS.md T3.8, D32). Print ×6.

Purpose: a short wall that keeps the folded Y loom off the Y belt: six segments in a row on
the baseboard, 100 mm apart, with the wall's loom-side face 42 mm from the right shaft axis.
The foot extends toward the belt; two 4×25 countersunk wood screws go through bosses on it.
The rails are not pre-drilled: lay them out with a tape and mark the screws through the foot.

Frame: x across (the wall's loom-side face at x = 0, wall toward -x, foot further toward -x),
y along the segment from 0, z up; printed foot down as modeled.

Hardware: 2 × 4×25 countersunk wood screws.
Print: PLA or PETG; 0.2 mm; 3 perimeters; 20 % infill; foot down; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube

from plotzker.params import LOOM, WOOD_SCREW, YDrive
from plotzker.parts.wood_screw import wood_screw_boss, wood_screw_hole

if TYPE_CHECKING:
    from pythonscad import Solid

FOOT_T = YDrive.foot_t  #: same 6 mm foot as the other baseboard parts


def screw_y() -> tuple[float, float]:
    """The two screws' y, from each end."""
    inset = WOOD_SCREW.boss_d / 2 + 0.5
    return (inset, LOOM.rail_len - inset)


def loom_rail() -> Solid:
    """One rail segment."""
    t, w = LOOM.rail_t, LOOM.foot_w
    wall = cube([t, LOOM.rail_len, LOOM.rail_h]).translate([-t, 0, 0])
    foot = cube([w, LOOM.rail_len, FOOT_T]).translate([-t - w, 0, 0])
    xs = -t - w / 2
    body = wall | foot
    for y in screw_y():
        body = body | wood_screw_boss(xs, y)
    for y in screw_y():
        body = body - wood_screw_hole(xs, y)
    return body
