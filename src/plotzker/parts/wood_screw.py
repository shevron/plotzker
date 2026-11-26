"""Boss and countersunk hole for the 4 × 25 mm wood screws that fix printed parts to the
baseboard (``params.WOOD_SCREW``). Frame: the part's foot is on z = 0 (print bed), screw
heads on top; the boss is as thick as the long screws need (the foot alone is too thin)."""

from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE
from pythonscad import cylinder

from plotzker.params import WOOD_SCREW

if TYPE_CHECKING:
    from pythonscad import Solid


def wood_screw_boss(x: float, y: float) -> Solid:
    """Round boss on the foot at ``(x, y)``, ``WOOD_SCREW.boss_t`` thick."""
    return cylinder(d=WOOD_SCREW.boss_d, h=WOOD_SCREW.boss_t, fn=FN_HOLE).translate([x, y, 0])


def wood_screw_hole(x: float, y: float) -> Solid:
    """Clearance hole with a 90° countersink in the boss's top face (the screw head sits
    flush with the top of the boss)."""
    w = WOOD_SCREW
    top = w.boss_t
    through = cylinder(d=w.hole_d, h=top + 2, fn=FN_HOLE).translate([x, y, -1])
    cone = cylinder(d1=w.hole_d, d2=w.sink_d, h=w.sink_h, fn=FN_HOLE).translate([x, y, top - w.sink_h])
    above = cylinder(d=w.sink_d, h=1, fn=FN_HOLE).translate([x, y, top])
    return through | cone | above
