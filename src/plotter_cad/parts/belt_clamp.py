"""Belt clamp cap (STATUS.md T3.2, D27). Print ×4 for Y (2 per gantry bracket) + ×2 for X.

Purpose: clamps one end of a belt against the flat underside of a gantry end bracket or of
the carriage's rear block. The cap has a groove between two rails: the groove holds the belt
sideways, its floor carries small ridges that sit in the tooth gaps so the belt can't slip,
and the rails press on the flat underside, which sets the squeeze (belt less 0.3 mm).

  section across the belt:     bracket ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ← flat underside (belt back)
                                  rail ▓▓▓▓└belt┘▓▓▓▓
                                  cap  ▔⊕▔▔▔ˆˆˆ▔▔▔⊕▔   ← groove 1.08 deep, ridges in the
                                                           tooth gaps

Frame: belt center at x = 0, clamp starts at y = 0 and runs +y, bottom on z = 0 (print
orientation: rails and ridges up, no supports or bridges). In an assembly the cap hangs
below the flat underside, its rails touching it.

Hardware per cap: 2 × M3×14 ISO 4762 into M3 nuts pressed into the bracket / carriage.
Print: PETG or PLA; 0.12–0.16 mm layers (fine ridges); 4 perimeters; 100 % infill;
flat side down; no supports.
"""

import math
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from plotter_cad.geometry import EPS, FN_HOLE, handle, set_handles
from plotter_cad.hardware import GT2
from plotter_cad.params import CLAMP, TOL

if TYPE_CHECKING:
    from pythonscad import Solid


def belt_clamp() -> Solid:
    """One belt clamp cap, in print orientation."""
    c = CLAMP
    belt_zone = GT2.width - 0.4  # ridges stay inside the groove
    plate = cube([c.w, c.length, c.t]).translate([-c.w / 2, 0, 0])
    rail_w = (c.w - c.channel_w) / 2
    rails = [
        cube([rail_w, c.length, c.channel_d + EPS]).translate(
            [sx * (c.channel_w + rail_w) / 2 - rail_w / 2, 0, c.t - EPS]
        )
        for sx in (-1, 1)
    ]
    ridges = [
        cube([belt_zone, c.ridge_w, c.ridge_h + EPS]).translate(
            [-belt_zone / 2, i * GT2.pitch + (GT2.pitch - c.ridge_w) / 2, c.t - EPS]
        )
        for i in range(math.floor(c.length / GT2.pitch))
    ]
    holes = [
        cylinder(d=TOL.bolt_hole_d(3), h=c.total_t + 2, fn=FN_HOLE).translate(
            [sx * c.screw_dx, c.length / 2, -1]
        )
        for sx in (-1, 1)
    ]
    # "mount": the rail tops, where the cap meets the flat underside it clamps against
    return set_handles((plate | rails | ridges) - holes, mount=handle([0, 0, c.total_t]))
