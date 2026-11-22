"""ZRIB guard strap: the minimal cover under the ZRIB's long edges (STATUS.md T3.7). Print ×2.

Purpose: a flat bar that joins the feet of one hanger's two legs below the heat sinks, so
the board edge can't be touched from below and the hanger can't spread. It leaves the
board open above and around (exposed electronics, airflow). It is fitted after the ZRIB
(the board is lifted in from below between the legs first).

Frame: flat on the bed, lengthwise along x, hole centers at x = ±(leg center), 9 mm wide.

Hardware per strap: 2 × M3×12 ISO 4762 into the nuts in the hanger legs.
Print: PETG; 0.2 mm layers; 4 perimeters; 40 % infill; flat; no supports.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from plotzker.geometry import FN_HOLE
from plotzker.params import TOL, ZMOUNT

if TYPE_CHECKING:
    from pythonscad import Solid


def zrib_guard() -> Solid:
    """The strap, flat on the bed."""
    m = ZMOUNT
    length = 2 * m.leg_u[1]
    bar = cube([length, m.leg_t, m.strap_t]).translate([-length / 2, 0, 0])
    holes = [
        cylinder(d=TOL.bolt_hole_d(3), h=m.strap_t + 2, fn=FN_HOLE).translate(
            [sx * m.strap_screw_u, m.leg_t / 2, -1]
        )
        for sx in (-1, 1)
    ]
    for hole in holes:
        bar = bar - hole
    return bar
