"""Ball and linear bearings. Dimensions in mm."""

from typing import TYPE_CHECKING, NamedTuple

from pythonscad import cylinder

if TYPE_CHECKING:
    from pythonscad import Solid


class Bearing(NamedTuple):
    """Bearing envelope: bore, outer diameter, width (length for linear bearings)."""

    bore: float
    outer_dia: float
    width: float


B608 = Bearing(8, 22, 7)
B625 = Bearing(5, 16, 5)
B623 = Bearing(3, 10, 4)
LM6UU = Bearing(6, 12, 19)
LM8UU = Bearing(8, 15, 24)
LM10UU = Bearing(10, 19, 29)


def bearing(spec: Bearing) -> Solid:
    """Generic bearing. Origin: center of one face, axis +Z."""
    body = cylinder(d=spec.outer_dia, h=spec.width, fn=48)
    bore = cylinder(d=spec.bore, h=spec.width + 2, fn=32).translate([0, 0, -1])
    return (body - bore).color("LightSteelBlue")
