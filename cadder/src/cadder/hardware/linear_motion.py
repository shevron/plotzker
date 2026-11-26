"""Linear motion: smooth shafts, SK10 shaft supports, SCS10UU bearing blocks.

Vendor table values and measurements. Dimensions in mm.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull, linear_extrude, polygon

from cadder.geometry import EPS

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class Shaft:
    """Smooth hardened shaft (optical axis), cut to ``length``."""

    length: float
    dia: float = 10


@dataclass(frozen=True)
class Sk10Spec:
    """SK10 shaft end support (vendor symbol in brackets)."""

    shaft_dia: float = 10  #: [d1] shaft diameter
    shaft_height: float = 20  #: [h] shaft center above the mounting surface (confirmed)
    side: float = 21  #: [E] center to side (= width / 2)
    width: float = 42  #: [W] overall width, across the shaft
    length: float = 13.1  #: [L] thickness along the shaft (measured; the table says 14)
    height: float = 37.5  #: [F] overall height
    base_thickness: float = 6  #: [G] base flange thickness
    body_width: float = 18  #: [P] width of the upright body
    #: [B] mounting-hole spacing: from the measured 2 mm between hole edge and narrow edge
    #: (hole Ø5.5, centered along the length); the vendor table says 32
    hole_pitch: float = 32.5
    base_chamfer: float = 1  #: measured roughly: both narrow edges. ASSUMED: top edges
    hole_dia: float = 5.5  #: [S] mounting holes (2 × M5)
    clamp_screw_size: float = 4  #: clamping bolt
    mount_screw_size: float = 5  #: mounting bolts
    mass_g: float = 24


@dataclass(frozen=True)
class Scs10uuSpec:
    """SCS10UU linear bearing block (vendor table; height and top face measured)."""

    shaft_dia: float = 10
    shaft_height: float = 13  #: [h] shaft center above the block base
    width: float = 40  #: [W] across the shaft
    length: float = 35  #: [L] along the shaft
    height: float = 26.5  #: [F] overall height (measured; the table says 26)
    top_thickness: float = 8  #: [T] top mounting section thickness
    hole_pitch_x: float = 28  #: [B] top hole spacing across the shaft
    hole_pitch_y: float = 21  #: [C] top hole spacing along the shaft
    top_hole_screw_size: float = 5  #: [S1] top holes, M5 threaded
    top_hole_depth: float = 12  #: [L1] M5 thread depth
    base_hole_dia: float = 4.3  #: [S2] base holes (M4 from below)
    mass_g: float = 92
    # Top face (measured): two raised flats along the full length, one each side of
    # the shaft, with a shallow recess between them; the M5 holes fall inside the flats.
    flat_width: float = 10
    recess_width: float = 17
    recess_depth: float = 1

    @property
    def top_chamfer(self) -> float:
        """Chamfer on each edge of each flat (0.75). ASSUMED: even split."""
        return (self.width - 2 * self.flat_width - self.recess_width) / 4

    @property
    def flat_x(self) -> float:
        """Flat center across the shaft (bracket contact strips): 14."""
        return self.recess_width / 2 + self.top_chamfer + self.flat_width / 2


SK10_SPEC = Sk10Spec()
SCS10UU_SPEC = Scs10uuSpec()


def shaft(spec: Shaft, length: float | None = None) -> Solid:
    """A shaft (``length`` overrides the spec's). Origin: start of the shaft on its axis; runs
    along +Y."""
    length_value = spec.length if length is None else length
    return cylinder(d=spec.dia, h=length_value, fn=32).rotate([-90, 0, 0]).color("WhiteSmoke")


def sk10() -> Solid:
    """SK10. Origin: mounting surface under the shaft axis, at mid-thickness; shaft along Y."""
    chamfer = SK10_SPEC.base_chamfer
    base = hull(
        cube([SK10_SPEC.width - 2 * chamfer, SK10_SPEC.length, SK10_SPEC.base_thickness]).translate(
            [-SK10_SPEC.width / 2 + chamfer, -SK10_SPEC.length / 2, 0]
        ),
        cube([SK10_SPEC.width, SK10_SPEC.length, SK10_SPEC.base_thickness - chamfer]).translate(
            [-SK10_SPEC.width / 2, -SK10_SPEC.length / 2, 0]
        ),
    )
    body = base | cube([SK10_SPEC.body_width, SK10_SPEC.length, SK10_SPEC.height]).translate(
        [-SK10_SPEC.body_width / 2, -SK10_SPEC.length / 2, 0]
    )
    bore = (
        cylinder(d=SK10_SPEC.shaft_dia, h=SK10_SPEC.length + 2, center=True, fn=32)
        .rotate([90, 0, 0])
        .translate([0, 0, SK10_SPEC.shaft_height])
    )
    slit = cube([1, SK10_SPEC.length + 2, SK10_SPEC.height]).translate(
        [-0.5, -SK10_SPEC.length / 2 - 1, SK10_SPEC.shaft_height]
    )
    holes = [
        cylinder(d=SK10_SPEC.hole_dia, h=SK10_SPEC.base_thickness + 2, fn=24).translate(
            [sx * SK10_SPEC.hole_pitch / 2, 0, -1]
        )
        for sx in (-1, 1)
    ]
    return (body - bore - slit - holes).color("Gainsboro")


def scs10uu() -> Solid:
    """SCS10UU. Origin: block base plane under the shaft axis, at mid-length; shaft along Y."""
    chamfer = SCS10UU_SPEC.top_chamfer
    recess = polygon(
        [
            [-SCS10UU_SPEC.recess_width / 2 - chamfer, EPS],
            [SCS10UU_SPEC.recess_width / 2 + chamfer, EPS],
            [SCS10UU_SPEC.recess_width / 2, -SCS10UU_SPEC.recess_depth],
            [-SCS10UU_SPEC.recess_width / 2, -SCS10UU_SPEC.recess_depth],
        ]
    ).translate([0, SCS10UU_SPEC.height, 0])
    edge_chamfers = [
        polygon([[0, EPS], [-sx * chamfer, EPS], [0, -chamfer]]).translate(
            [sx * SCS10UU_SPEC.width / 2, SCS10UU_SPEC.height, 0]
        )
        for sx in (-1, 1)
    ]
    top_cuts = linear_extrude([recess, *edge_chamfers], height=SCS10UU_SPEC.length + 2, center=True).rotate([90, 0, 0])
    # the block is modeled with its LM10UU bushing in place, so the bore is the shaft's
    bore = (
        cylinder(d=SCS10UU_SPEC.shaft_dia, h=SCS10UU_SPEC.length + 2, center=True, fn=40)
        .rotate([90, 0, 0])
        .translate([0, 0, SCS10UU_SPEC.shaft_height])
    )
    holes = [
        cylinder(d=SCS10UU_SPEC.top_hole_screw_size * 0.85, h=SCS10UU_SPEC.top_hole_depth + 1, fn=16).translate(
            [
                sx * SCS10UU_SPEC.hole_pitch_x / 2,
                sy * SCS10UU_SPEC.hole_pitch_y / 2,
                SCS10UU_SPEC.height - SCS10UU_SPEC.top_hole_depth,
            ]
        )
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]
    block = cube([SCS10UU_SPEC.width, SCS10UU_SPEC.length, SCS10UU_SPEC.height]).translate(
        [-SCS10UU_SPEC.width / 2, -SCS10UU_SPEC.length / 2, 0]
    )
    return (block - top_cuts - bore - holes).color("Silver")
