"""v1 pen holder on the carriage: body, slide, rod, servo, horn, screws and a pen (T3.6).

:func:`pen_holder_items` builds the head in the head frame of ``params.PenHolder``;
:func:`pen_holder_assembly` places it in the carriage-local frame. Not printable.
"""

import math
from typing import TYPE_CHECKING

from pythonscad import cylinder

from plotter_cad.assemblies.carriage import carriage_assembly
from plotter_cad.geometry import FN
from plotter_cad.hardware import FT90M, hex_nut, servo_ft90m, servo_horn, shcs, vslot_x
from plotter_cad.params import BEAM, CARRIAGE, FRAME, PEN, TOL, TOOL_PLATE
from plotter_cad.parts.pen_holder_body import pen_holder_body_head
from plotter_cad.parts.pen_slide import pen_slide_head

if TYPE_CHECKING:
    from pythonscad import Solid

PEN_LENGTH = 120.0  #: pen model length


def pen_holder_items(pen_up: bool = False, pen_d: float = 10.0) -> dict[str, Solid]:
    """The pen holder in the head frame, by name. ``pen_up`` lifts the slide and the pen."""
    p = PEN
    lift = p.lift if pen_up else 0.0
    pin_z = p.pin_up_z if pen_up else p.pin_down_z
    angle = math.degrees(math.asin((pin_z - p.shaft_z) / p.horn_r))
    d_horn0 = p.horn_d[0]
    rod = cylinder(d=p.rod_d, h=p.rod_len, fn=32).translate(
        [p.rod_x, p.rod_d_pos, p.upper_arm_top - p.rod_len]
    )
    screw_head_d = p.plate_d[1] - 3
    items = {
        "body": pen_holder_body_head().color("SteelBlue"),
        "slide": pen_slide_head().translate([0, 0, lift]).color("Orange"),
        "rod": rod.color("Silver"),
        "servo": servo_ft90m()
        .rotate([0, 90, 270])
        .translate([p.servo_x, p.servo_front_d, p.servo_center_z]),
        "horn": servo_horn()
        .rotate([0, 0, -angle])
        .rotate([-90, 0, 0])
        .translate([p.servo_x, d_horn0, p.shaft_z]),
        "pin": cylinder(d=p.pin_d, h=p.pin_reach + p.horn_t, fn=16)
        .rotate([-90, 0, 0])
        .translate(
            [
                p.servo_x + p.horn_r * math.cos(math.radians(angle)),
                d_horn0 - p.pin_reach,
                p.shaft_z + p.horn_r * math.sin(math.radians(angle)),
            ]
        )
        .color("DimGray"),
    }
    for i, sx in enumerate((-1, 1)):
        items[f"clamp_screw_{i}"] = (
            shcs(3, 10)
            .rotate([-90, 0, 0])
            .translate(
                [
                    sx * TOOL_PLATE.screw_pitch / 2,
                    screw_head_d,
                    TOOL_PLATE.bottom_z + TOOL_PLATE.screw_z,
                ]
            )
        )
    bar_front = p.yoke_bar_d[1]
    zc = sum(p.yoke_z) / 2
    pen_front = p.pen_axis_d(pen_d) + pen_d / 2
    items["pen"] = (
        cylinder(d=pen_d, h=PEN_LENGTH, fn=FN)
        .translate([p.pen_x, p.pen_axis_d(pen_d), FRAME.bed_top_z + lift])
        .color("Crimson")
    )
    items["thumbscrew"] = (
        shcs(5, p.clamp_screw_len)
        .rotate([-90, 0, 0])
        .translate([p.pen_x, pen_front + p.clamp_screw_len, zc + lift])
    )
    items["thumbscrew_nut"] = (
        hex_nut(5)
        .rotate([-90, 0, 0])
        .translate([p.pen_x, bar_front - TOL.nut_trap_h(5), zc + lift])
    )
    return items


def pen_holder_assembly(pen_up: bool = False, pen_d: float = 10.0) -> list[Solid]:
    """The pen holder in the carriage-local frame (carriage front face at y = plate_front_y)."""
    return [
        item.mirror([0, 1, 0]).translate([0, CARRIAGE.plate_front_y, 0])
        for item in pen_holder_items(pen_up, pen_d).values()
    ]


def pen_holder_fit_check() -> list[Solid]:
    """The carriage with its pen holder on a piece of the beam, pen up."""
    beam = vslot_x(240, BEAM.size).translate([-120, -BEAM.depth / 2, BEAM.bottom_z])
    return [*carriage_assembly(), beam, *pen_holder_assembly(pen_up=True)]


__all__ = ["FT90M", "pen_holder_assembly", "pen_holder_fit_check", "pen_holder_items"]
