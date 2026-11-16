"""Metric fasteners: ISO 4762 socket head cap screws, ISO 4032 hex nuts,
ISO 7089 washers. Dimensions in mm.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder

from plotter_cad.geometry import cos_deg

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class MetricSize:
    """Dimensions of the fasteners of one metric thread size."""

    m: float  #: nominal thread diameter
    head_d: float  #: SHCS head diameter
    head_h: float  #: SHCS head height
    nut_af: float  #: hex nut across flats
    nut_h: float  #: hex nut height
    washer_od: float
    washer_t: float

    @property
    def nut_ac(self) -> float:
        """Hex nut across corners."""
        return self.nut_af / cos_deg(30)


_SIZES = (
    MetricSize(2.5, head_d=4.5, head_h=2.5, nut_af=5.0, nut_h=2.0, washer_od=5.0, washer_t=0.5),
    MetricSize(3, head_d=5.5, head_h=3.0, nut_af=5.4, nut_h=2.25, washer_od=7.0, washer_t=0.5),
    MetricSize(4, head_d=7.0, head_h=4.0, nut_af=7.0, nut_h=3.2, washer_od=9.0, washer_t=0.8),
    MetricSize(5, head_d=8.5, head_h=5.0, nut_af=8.0, nut_h=4.7, washer_od=10.0, washer_t=1.0),
)
METRIC: dict[float, MetricSize] = {size.m: size for size in _SIZES}

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
    head = cylinder(d=size.head_d, h=size.head_h, fn=24)
    shank = cylinder(d=m, h=length, fn=16).translate([0, 0, -length])
    return (head | shank).color("DimGray")


def countersunk_screw(m: float, length: float, head_d: float) -> Solid:
    """Countersunk (90°) screw. Origin: center of the head's top face; shank points down -Z."""
    h = (head_d - m) / 2
    head = cylinder(d1=m, d2=head_d, h=h, fn=24).translate([0, 0, -h])
    shank = cylinder(d=m, h=length - h + 0.01, fn=16).translate([0, 0, -length])
    return (head | shank).color("DimGray")


def hex_nut(m: float) -> Solid:
    """Hex nut. Origin: center of the bottom face, axis +Z."""
    size = metric(m)
    body = cylinder(d=size.nut_ac, h=size.nut_h, fn=6)
    bore = cylinder(d=m, h=size.nut_h + 2, fn=16).translate([0, 0, -1])
    return (body - bore).color("Silver")


def washer(m: float) -> Solid:
    """Washer. Origin: center of the bottom face, axis +Z."""
    size = metric(m)
    body = cylinder(d=size.washer_od, h=size.washer_t, fn=24)
    bore = cylinder(d=m + 0.3, h=3, fn=16).translate([0, 0, -1])
    return (body - bore).color("Silver")


def t_nut(m: float, thickness: float = 4.0) -> Solid:
    """Drop-in T-nut for the 6 mm slot of 2020/2040 V-slot (simplified plate).

    Origin: center of the top face; axis along Z, the plate lies in XY (long side along X).
    """
    plate = cube([11, 9.5, thickness]).translate([-5.5, -4.75, -thickness])
    bore = cylinder(d=m, h=thickness + 2, fn=16).translate([0, 0, -thickness - 1])
    return (plate - bore).color("Silver")


def spring(od: float, id_: float, length: float) -> Solid:
    """Compression spring as a plain tube. Origin: center of the bottom face, axis +Z."""
    return (
        cylinder(d=od, h=length, fn=32) - cylinder(d=id_, h=length + 2, fn=32).translate([0, 0, -1])
    ).color("SteelBlue")
