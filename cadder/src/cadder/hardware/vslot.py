"""20 mm series V-slot extrusion, POM V-wheels and eccentric spacers. Dimensions in mm.

The extrusion profiles are 2D sketches drawn as SVG files next to this module
(``vslot_2020.svg``, ``vslot_2040.svg``); :func:`vslot_profile` loads them and
:func:`vslot_x` / :func:`vslot_y` extrude them to length.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pythonscad import cylinder, linear_extrude

from cadder.geometry import load_sketch

if TYPE_CHECKING:
    from pythonscad import Solid

#: The profile sketches live next to this module.
SKETCH_DIR = Path(__file__).parent
#: Profile size (units along X, units along Y) → (sketch file, rotate a quarter turn).
#: The 2040 sketch is drawn upright (20 wide, 40 tall).
PROFILE_SKETCHES: dict[tuple[int, int], tuple[str, bool]] = {
    (1, 1): ("vslot_2020.svg", False),
    (1, 2): ("vslot_2040.svg", False),
    (2, 1): ("vslot_2040.svg", True),
}


@dataclass(frozen=True)
class VSlotSpec:
    """V-slot extrusion. The profile shapes are SVG sketches (:data:`PROFILE_SKETCHES`)."""

    unit: float = 20
    #: V-groove depth = slot lip thickness, as drawn in the sketches (vendor drawing);
    #: also shapes the wheel model.
    groove_d: float = 1.85
    #: kg/m, from the sketch areas (161 and 296 mm²) × 2.70 g/cm³ aluminum
    mass_per_m_2020: float = 0.44
    mass_per_m_4020: float = 0.80


@dataclass(frozen=True)
class VWheelSpec:
    """Solid POM V-wheel on 2 × 625 bearings (OpenBuilds "Solid V Wheel" type)."""

    od: float = 24  #: outer diameter (user)
    width: float = 10  #: (user)
    bore: float = 5  #: 625 bearing bore
    #: Wheel axis to the extrusion face it rides on: (39.7 - 20) / 2 from the standard
    #: 39.7 mm wheel spacing across a 20 mm V-slot. ASSUMED
    axis_to_face: float = 9.85
    spacer_len: float = 6  #: plain spacer between plate and wheel. ASSUMED


@dataclass(frozen=True)
class EccentricSpacerSpec:
    """Eccentric spacer (2 used on the carriage's bottom wheels, D21). Measured."""

    length: float = 7.8  #: hex body length
    offset: float = 0.7  #: bore offset from the boss axis (±0.7 → 1.4 mm), approx.
    hex_af: float = 10
    hex_ac: float = 11.4
    bore: float = 5  #: M5 bolt through it
    boss_d: float = 7.1  #: boss that sits in the carriage plate (measured)
    boss_len: float = 2.1  #: boss length into the carriage plate
    back_len: float = 0.5  #: short boss on the wheel side of the hex (approx.)

    @property
    def stack(self) -> float:
        """Plate face → wheel bearing face (8.3). The plain top wheels must match it."""
        return self.length + self.back_len


VSLOT = VSlotSpec()
VWHEEL = VWheelSpec()
ECCENTRIC = EccentricSpacerSpec()


def vslot_profile(n: tuple[int, int] = (1, 1)) -> Solid:
    """2D profile of ``n[0] × n[1]`` units (e.g. ``(2, 1)`` = a 2040 lying 40 wide, 20 tall).

    Origin: lower-left corner of the profile. The profile is loaded from the SVG sketch
    of that size (:data:`PROFILE_SKETCHES`); to add a size, draw its sketch and register it.
    """
    try:
        name, quarter_turn = PROFILE_SKETCHES[n[0], n[1]]
    except KeyError:
        known = ", ".join(f"{a}×{b}" for a, b in sorted(PROFILE_SKETCHES))
        raise ValueError(f"No V-slot sketch for {n[0]}×{n[1]} units; known: {known}") from None
    profile = load_sketch(SKETCH_DIR / name)
    if quarter_turn:
        # lay the upright sketch flat, back into the +X +Y quadrant
        profile = profile.rotate([0, 0, 90]).translate([n[0] * VSLOT.unit, 0, 0])
    return profile


def vslot_x(length: float, size: tuple[int, int] = (1, 1)) -> Solid:
    """Extrusion along +X. Origin: lower-front-left corner of the profile at x = 0.

    ``size`` = (units deep along Y, units tall along Z); the upright 4020 X beam is
    ``vslot_x(length, (1, 2))``.
    """
    return linear_extrude(vslot_profile(size), height=length).rotate([90, 0, 90]).color("LightGray")


def vslot_y(length: float, size: tuple[int, int] = (1, 1)) -> Solid:
    """Extrusion along +Y, same profile convention (units along X, units along Z)."""
    return (
        linear_extrude(vslot_profile(size), height=length)
        .rotate([90, 0, 0])
        .translate([0, length, 0])
        .color("LightGray")
    )


def vwheel() -> Solid:
    """V-wheel. Origin: wheel center; axis along Y (rides on X-direction rails)."""
    w = VWHEEL
    inner_d = w.od - 2 * VSLOT.groove_d
    cone = cylinder(d1=w.od, d2=inner_d, h=w.width / 2 - 0.5, fn=48)
    body = cylinder(d=inner_d, h=w.width, center=True, fn=48) | cone | cone.mirror([0, 0, 1])
    bore = cylinder(d=w.bore, h=w.width + 2, center=True, fn=24)
    return (body - bore).rotate([90, 0, 0]).color("#202020")


def eccentric_spacer(rot: float = 0) -> Solid:
    """Eccentric spacer.

    Origin: on the boss axis at the plate-side face of the hex; the boss points -Y
    (into the plate), the hex and wheel-side boss extend +Y. ``rot`` is the
    adjustment angle; the bore sits ``offset`` off the boss axis.
    """
    e = ECCENTRIC
    body = (
        cylinder(d=e.boss_d, h=e.boss_len, fn=32).translate([0, 0, -e.boss_len])
        | cylinder(d=e.hex_ac, h=e.length, fn=6)
        | cylinder(d=e.boss_d, h=e.stack, fn=32)
    )
    bore = cylinder(d=e.bore, h=20, fn=20).translate([e.offset, 0, -5]).rotate([0, 0, rot])
    return (body - bore).rotate([-90, 0, 0]).color("Gold")
