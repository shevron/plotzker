"""NEMA17 stepper motor and FeeTech FT90M hobby servo. Dimensions in mm."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull, linear_extrude, square

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class Nema17Spec:
    """NEMA17 stepper dimensions."""

    width: float = 42.3
    length: float = 39.2  #: body length, typical motor on hand (measured)
    length_short: float = 33.5  #: shorter motors on hand (measured)
    length_max: float = 48  #: clearance envelope: longest common NEMA17. DESIGN
    hole_pitch: float = 31  #: M3 holes, square pattern
    hole_depth: float = 4.5  #: ASSUMED
    boss_d: float = 22  #: pilot boss
    boss_h: float = 2
    shaft_d: float = 5
    shaft_len: float = 22.6  #: from the face, 39.2 mm motor (measured)
    #: Shortest shaft on hand (33.5 mm motor, measured): belt lines must work with it.
    shaft_len_min: float = 19
    shaft_flat: float = 0.5  #: D-cut depth. ASSUMED
    chamfer: float = 4  #: corner chamfer (visual)
    mass_g: float = 280  #: ASSUMED


@dataclass(frozen=True)
class ServoSpec:
    """FeeTech FT90M micro servo (metal gears, digital; T3.6)."""

    #: L × W × H below the gear boss: 25.5 overall (measured, excludes the spline) minus
    #: the 3.8 boss.
    body: tuple[float, float, float] = (23.2, 12.1, 21.7)
    tab_len: float = 32.5  #: overall length across the tabs (measured)
    tab_t: float = 1.6  #: measured
    tab_z: float = 17.0  #: tab underside above the body bottom (measured)
    hole_pitch: float = 28.5  #: measured
    hole_d: float = 1.8  #: measured
    shaft_offset: float = 5.9  #: shaft axis from the body end (measured)
    top_h: float = 3.8  #: gear boss above the body (measured)
    shaft_h: float = 3.0  #: spline above the gear housing. ASSUMED
    mass_g: float = 13.5  #: vendor figure, confirmed by the user
    #: Single-sided horn (supplied with the servo, measured): shaft center to tip, and
    #: 4 holes along the arm; the last is ``horn_last_hole`` from the tip.
    horn_len: float = 17.0
    horn_hole_pitch: float = 2.5
    horn_holes: int = 4
    horn_last_hole: float = 1.9


NEMA17 = Nema17Spec()
FT90M = ServoSpec()


def nema17(length: float = NEMA17.length) -> Solid:
    """NEMA17. Origin: center of the mounting face (base of the boss); shaft +Z, body -Z."""
    n = NEMA17
    outline = square([n.width - 2 * n.chamfer] * 2, center=True).offset(
        delta=n.chamfer, chamfer=True
    )
    body = linear_extrude(outline, height=length).translate([0, 0, -length])
    holes = [
        cylinder(d=3, h=n.hole_depth + 1, fn=12).translate(
            [sx * n.hole_pitch / 2, sy * n.hole_pitch / 2, -n.hole_depth]
        )
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]
    flat = cube([5, 10, 16]).translate([n.shaft_d / 2 - n.shaft_flat, -5, n.shaft_len - 15])
    shaft = cylinder(d=n.shaft_d, h=n.shaft_len, fn=24) - flat
    boss = cylinder(d=n.boss_d, h=n.boss_h, fn=48)
    return (body - holes).color("#2a2a2a") | (boss | shaft).color("Silver")


def servo_ft90m() -> Solid:
    """Servo. Origin: center of the body's bottom face; shaft at the +X end, pointing +Z."""
    s = FT90M
    length, width, height = s.body
    body = cube([length, width, height]).translate([-length / 2, -width / 2, 0])
    tab_holes = [
        cylinder(d=s.hole_d, h=s.tab_t + 2, fn=12).translate(
            [sx * s.hole_pitch / 2, 0, s.tab_z - 1]
        )
        for sx in (-1, 1)
    ]
    tabs = (
        cube([s.tab_len, width, s.tab_t]).translate([-s.tab_len / 2, -width / 2, s.tab_z])
        - tab_holes
    )
    shaft_x = length / 2 - s.shaft_offset
    gear_housing = cylinder(d=width, h=s.top_h, fn=32).translate([shaft_x, 0, height])
    spline = cylinder(d=4.8, h=s.shaft_h, fn=16).translate([shaft_x, 0, height + s.top_h])
    return (body | tabs | gear_housing).color("RoyalBlue") | spline.color("White")


def servo_horn() -> Solid:
    """FT90M single-sided horn. Origin: shaft axis on the horn's back face; arm toward +X,
    thickness along +Z (``horn_t`` ASSUMED 1.8 mm).
    """
    s = FT90M
    thickness = 1.8
    hub = cylinder(d=7, h=thickness, fn=32)
    arm = hull(
        cylinder(d=7, h=thickness, fn=32),
        cylinder(d=3.4, h=thickness, fn=24).translate([s.horn_len - 1.7, 0, 0]),
    )
    holes = [
        cylinder(d=1.2, h=thickness + 2, fn=12).translate(
            [s.horn_len - s.horn_last_hole - i * s.horn_hole_pitch, 0, -1]
        )
        for i in range(s.horn_holes)
    ]
    return ((hub | arm) - holes).color("WhiteSmoke")
