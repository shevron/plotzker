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

FOOT_T = YDrive.foot_thickness  #: same 6 mm foot as the other baseboard parts


def screw_y() -> tuple[float, float]:
    """The two screws' y, from each end."""
    inset = WOOD_SCREW.boss_dia / 2 + 0.5
    return inset, LOOM.rail_length - inset


def loom_rail() -> Solid:
    """One rail segment."""
    thickness, width = LOOM.rail_thickness, LOOM.foot_width
    wall = cube([thickness, LOOM.rail_length, LOOM.rail_height]).translate([-thickness, 0, 0])
    foot = cube([width, LOOM.rail_length, FOOT_T]).translate([-thickness - width, 0, 0])
    screw_x = -thickness - width / 2
    body = wall | foot
    for y in screw_y():
        body = body | wood_screw_boss(screw_x, y)
    for y in screw_y():
        body = body - wood_screw_hole(screw_x, y)
    return body
