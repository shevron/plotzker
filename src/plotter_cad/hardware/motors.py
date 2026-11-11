"""NEMA17 stepper motor and SG90-class hobby servo. Dimensions in mm."""

from dataclasses import dataclass

from pythonscad import cube, cylinder, linear_extrude, square


@dataclass(frozen=True)
class Nema17Spec:
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
    """SG90-class servo. All values ASSUMED until the servo model is known (T3.6)."""

    body: tuple[float, float, float] = (22.8, 12.2, 22.5)  #: L × W × H
    tab_len: float = 32.3  #: overall length across the tabs
    tab_t: float = 2.5
    tab_z: float = 15.9  #: tab underside above the body bottom
    hole_pitch: float = 27.8
    hole_d: float = 2.0
    shaft_offset: float = 5.9  #: shaft axis from the body end
    top_h: float = 4.5  #: gear housing above the body
    shaft_h: float = 3.0  #: spline above the gear housing


NEMA17 = Nema17Spec()
SG90 = ServoSpec()


def nema17(length: float = NEMA17.length):
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


def servo_sg90():
    """Servo. Origin: center of the body's bottom face; shaft at the +X end, pointing +Z."""
    s = SG90
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
