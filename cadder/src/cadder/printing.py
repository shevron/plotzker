"""Print tolerances and features for FDM-printed parts.

:class:`Tolerances` turns nominal sizes into hole and pocket sizes; :func:`nut_slot` is a
hex-profile pocket for a nut pressed in sideways.

Nut slot: a nut that is pressed into a slot from an edge sits **flat-first** (a flat faces the
pressing direction, so a thumb pushes straight onto it) and must not turn when the bolt is
tightened. A plain rectangular slot wide enough for the corners lets it spin; this pocket
instead follows the hex outline at the bottom (flat floor, two 60° sloped sides up to the
corners), which holds the nut like an axial hex pocket, and continues with straight walls up to
the entrance. It needs no supports: the sloped sides are 30° from vertical.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from cadder.geometry import EPS, cos_deg
from cadder.hardware.fasteners import metric

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class Tolerances:
    """Print tolerances: how much bigger than nominal to make holes, traps and gaps (mm).

    The defaults suit PETG on a 0.4–0.6 mm nozzle; a project measures its own prints and
    overrides what differs.
    """

    bolt: float = 0.4  #: clearance-hole oversize: M3 → 3.4, M5 → 5.4
    slide: float = 0.2  #: sliding fit (diametral)
    press: float = 0.0  #: press fit (0 to -0.1)
    nut: float = 0.1  #: nut trap: across-flats oversize (snug: nuts are pressed in)
    #: hex-profile nut slot (:func:`nut_slot`): across-flats oversize, ~0.1 mm per side plus
    #: the ~0.1 mm the print comes out narrow
    nut_slot: float = 0.3
    nut_thickness: float = 0.1  #: nut trap: thickness oversize (the print comes out ~0.1 thicker)
    gap: float = 0.3  #: general clearance between mating printed parts
    min_wall: float = 1.6  #: 4 perimeters at 0.4 mm nozzle
    layer_height: float = 0.2
    nozzle_dia: float = 0.4
    nut_wall: float = 2.0  #: plastic that backs a pressed-in nut (takes the thrust or pull)

    def bolt_hole_dia(self, m: float) -> float:
        """Clearance hole for an M``m`` bolt."""
        return m + self.bolt

    def nut_trap_across_flats(self, m: float) -> float:
        """Across flats of a nut trap."""
        return metric(m).nut_across_flats + self.nut

    def nut_trap_across_corners(self, m: float) -> float:
        """Across corners of a nut trap (for a 6-sided cylinder)."""
        return self.nut_trap_across_flats(m) / cos_deg(30)

    def nut_trap_height(self, m: float) -> float:
        """Height (thickness) of a nut trap slot."""
        return metric(m).nut_height + self.nut_thickness

    def counterbore_dia(self, m: float) -> float:
        """Counterbore for a socket head cap screw head."""
        return metric(m).head_dia + 2 * self.bolt

    def slide_dia(self, d: float) -> float:
        """Hole diameter for a sliding fit on a ``d`` mm part."""
        return d + self.slide

    def press_dia(self, d: float) -> float:
        """Hole diameter for a press fit on a ``d`` mm part."""
        return d + self.press


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


def nut_slot(
    m: float,
    reach: float,
    axis: str,
    entrance: str,
    extra_thickness: float = 0,
    tol: Tolerances | None = None,
) -> Solid:
    """Pocket for an M``m`` nut, centered on the nut's center.

    ``axis``: the bolt's axis (``"x"``, ``"y"`` or ``"z"``); ``entrance``: the direction the
    nut is pressed in from, as a signed axis (``"+z"``, ``"-x"``...): the pocket's floor lies
    below the nut and the pocket runs out to ``reach`` mm from the nut's center toward the
    entrance. Combinations not in ``_ROTATIONS`` are added when needed. ``extra_thickness`` makes the
    pocket that much thicker (a long pocket whose print orientation makes it come out tight).
    ``tol``: the project's print tolerances (default: :class:`Tolerances`' defaults).
    """
    tol = tol or Tolerances()
    af = metric(m).nut_across_flats + tol.nut_slot  # across flats (the print comes out ~0.1 narrow)
    ac = af / cos_deg(30)
    t = tol.nut_trap_height(m) + extra_thickness
    hexagon = cylinder(d=ac, h=t, fn=6).rotate([90, 0, 0]).translate([0, t / 2, 0])
    walls = cube([ac, t, reach + EPS]).translate([-ac / 2, -t / 2, -EPS])
    return (hexagon | walls).rotate(list(_ROTATIONS[axis, entrance]))
