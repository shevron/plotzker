"""Metric fasteners: ISO 4762 socket head cap screws, ISO 4032 hex nuts,
ISO 7089 washers. Dimensions in mm.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from cadder.geometry import cos_deg

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class MetricSize:
    """Dimensions of the fasteners of one metric thread size."""

    size: float  #: nominal thread diameter
    head_dia: float  #: SHCS head diameter
    head_height: float  #: SHCS head height
    nut_across_flats: float  #: hex nut across flats
    nut_height: float  #: hex nut height
    washer_outer_dia: float
    washer_thickness: float

    @property
    def nut_across_corners(self) -> float:
        """Hex nut across corners."""
        return self.nut_across_flats / cos_deg(30)


_SIZES = (
    MetricSize(
        2.5,
        head_dia=4.5,
        head_height=2.5,
        nut_across_flats=5.0,
        nut_height=2.0,
        washer_outer_dia=5.0,
        washer_thickness=0.5,
    ),
    MetricSize(
        3,
        head_dia=5.5,
        head_height=3.0,
        nut_across_flats=5.4,
        nut_height=2.25,
        washer_outer_dia=7.0,
        washer_thickness=0.5,
    ),
    MetricSize(
        4,
        head_dia=7.0,
        head_height=4.0,
        nut_across_flats=7.0,
        nut_height=3.2,
        washer_outer_dia=9.0,
        washer_thickness=0.8,
    ),
    MetricSize(
        5,
        head_dia=8.5,
        head_height=5.0,
        nut_across_flats=8.0,
        nut_height=4.7,
        washer_outer_dia=10.0,
        washer_thickness=1.0,
    ),
)
METRIC: dict[float, MetricSize] = {size.size: size for size in _SIZES}

M2_5, M3, M4, M5 = _SIZES


def metric(m: float) -> MetricSize:
    """Fastener dimensions for thread size ``m`` (e.g. ``metric(3)``)."""
    try:
        return METRIC[m]
    except KeyError:
        raise ValueError(f"No fastener data for M{m}; known: {sorted(METRIC)}") from None


# --- models (fit checks and visuals only) -------------------------------------


def shcs(m: float, length: float) -> Solid:
    """Socket head cap screw.

    Origin: center of the underside of the head; shank points down -Z.
    """
    size = metric(m)
    head = cylinder(d=size.head_dia, h=size.head_height, fn=24)
    shank = cylinder(d=m, h=length, fn=16).translate([0, 0, -length])
    return (head | shank).color("DimGray")


def countersunk_screw(m: float, length: float, head_dia: float) -> Solid:
    """Countersunk (90°) screw. Origin: center of the head's top face; shank points down -Z."""
    h = (head_dia - m) / 2
    head = cylinder(d1=m, d2=head_dia, h=h, fn=24).translate([0, 0, -h])
    shank = cylinder(d=m, h=length - h + 0.01, fn=16).translate([0, 0, -length])
    return (head | shank).color("DimGray")


def hex_nut(m: float) -> Solid:
    """Hex nut. Origin: center of the bottom face, axis +Z."""
    size = metric(m)
    body = cylinder(d=size.nut_across_corners, h=size.nut_height, fn=6)
    bore = cylinder(d=m, h=size.nut_height + 2, fn=16).translate([0, 0, -1])
    return (body - bore).color("Silver")


def washer(m: float) -> Solid:
    """Washer. Origin: center of the bottom face, axis +Z."""
    size = metric(m)
    body = cylinder(d=size.washer_outer_dia, h=size.washer_thickness, fn=24)
    bore = cylinder(d=m + 0.3, h=3, fn=16).translate([0, 0, -1])
    return (body - bore).color("Silver")


def t_nut(m: float, thickness: float = 4.0) -> Solid:
    """Drop-in T-nut for the 6 mm slot of 2020/2040 V-slot (simplified plate).

    Origin: center of the top face; axis along Z, the plate lies in XY (long side along X).
    """
    plate = cube([11, 9.5, thickness]).translate([-5.5, -4.75, -thickness])
    bore = cylinder(d=m, h=thickness + 2, fn=16).translate([0, 0, -thickness - 1])
    return (plate - bore).color("Silver")


def spring(outer_dia: float, inner_dia: float, length: float) -> Solid:
    """Compression spring as a plain tube. Origin: center of the bottom face, axis +Z."""
    return (
        cylinder(d=outer_dia, h=length, fn=32) - cylinder(d=inner_dia, h=length + 2, fn=32).translate([0, 0, -1])
    ).color("SteelBlue")
