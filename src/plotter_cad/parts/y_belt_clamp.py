"""Belt clamp cap (STATUS.md T3.2). Print ×4 for Y (2 per gantry bracket) + ×2 for X (carriage).

Purpose: clamps one end of a belt into the channel under a gantry end bracket (or
the carriage's rear block). The belt's back bears on the channel ceiling; the cap
presses on the teeth, with small ridges that sit in the tooth gaps so the belt
can't slip.

  section across the belt:     bracket ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
                                       ▓▓▓▓└belt┘▓▓▓▓  ← channel 1.08 deep
                                  cap  ▔⊕▔▔▔ˆˆˆ▔▔▔⊕▔   ← ridges in the tooth gaps

Frame: belt center at x = 0, clamp starts at y = 0 and runs +y, bottom on z = 0
(print orientation: ridges up). In an assembly the cap is flipped onto the
bracket underside (ridges up = toward the belt teeth).

Hardware per cap: 2 × M3×10 ISO 4762 into M3 heat-set inserts in the bracket.
Print: PETG or PLA; 0.12–0.16 mm layers (fine ridges); 4 perimeters; 100 % infill;
flat side down; no supports.
"""

import math
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from plotter_cad.geometry import EPS, FN_HOLE
from plotter_cad.hardware import GT2
from plotter_cad.params import CLAMP, TOL

if TYPE_CHECKING:
    from pythonscad import Solid


def y_belt_clamp() -> Solid:
    """One belt clamp cap, in print orientation."""
    c = CLAMP
    belt_zone = GT2.width - 0.4  # ridges stay inside the 6.4 mm channel
    plate = cube([c.w, c.length, c.t]).translate([-c.w / 2, 0, 0])
    ridges = [
        cube([belt_zone, c.ridge_w, c.ridge_h + EPS]).translate(
            [-belt_zone / 2, i * GT2.pitch + (GT2.pitch - c.ridge_w) / 2, c.t - EPS]
        )
        for i in range(math.floor(c.length / GT2.pitch))
    ]
    holes = [
        cylinder(d=TOL.bolt_hole_d(3), h=c.t + 2, fn=FN_HOLE).translate(
            [sx * c.screw_dx, c.length / 2, -1]
        )
        for sx in (-1, 1)
    ]
    return (plate | ridges) - holes
