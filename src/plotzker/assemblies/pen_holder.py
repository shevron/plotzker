"""v1 pen holder on the carriage: body, slide, rod, servo, horn, screws and a pen (T3.6).

:func:`pen_holder_items` builds the head in the head frame of ``params.PenHolder``;
:func:`pen_holder_assembly` places it in the carriage-local frame. Not printable.
"""

import math
from typing import TYPE_CHECKING

from cadder.geometry import FN
from cadder.handles import get_handle, get_handles, shift_handle
from cadder.hardware import FT90M, hex_nut, servo_ft90m, servo_horn, shcs, vslot_x
from pythonscad import cylinder

from plotzker.assemblies.carriage import carriage_assembly
from plotzker.params import BEAM, CARRIAGE, FRAME, PEN
from plotzker.parts.pen_holder_body import pen_holder_body_head
from plotzker.parts.pen_slide import pen_slide_head

if TYPE_CHECKING:
    from pythonscad import Solid

PEN_LENGTH = 120.0  #: pen model length


def pen_holder_items(pen_up: bool = False, pen_d: float = 10.0) -> dict[str, Solid]:
    """The pen holder in the head frame, by name. ``pen_up`` lifts the slide and the pen."""
    p = PEN
    lift = p.lift if pen_up else 0.0
    pin_z = p.pin_up_z if pen_up else p.pin_down_z
    angle = math.degrees(math.asin((pin_z - p.shaft_z) / p.horn_r))
    body = pen_holder_body_head()
    slide = pen_slide_head().translate([0, 0, lift])
    horn = get_handle(body, "horn")
    items = {
        "body": body.color("SteelBlue"),
        "slide": slide.color("Orange"),
        "rod": cylinder(d=p.rod_d, h=p.rod_len, fn=32)
        .align(get_handle(body, "rod"))
        .color("Silver"),
        "servo": servo_ft90m().align(get_handle(body, "servo")),
        "horn": servo_horn().rotate([0, 0, -angle]).align(horn),
        "pin": cylinder(d=p.pin_d, h=p.pin_reach + p.horn_t, fn=16)
        .rotate([-90, 0, 0])
        .translate(
            [
                p.servo_x + p.horn_r * math.cos(math.radians(angle)),
                horn[1][3] - p.pin_reach,
                p.shaft_z + p.horn_r * math.sin(math.radians(angle)),
            ]
        )
        .color("DimGray"),
    }
    for i, screw in enumerate(get_handles(body, "clamp_screws")):
        items[f"clamp_screw_{i}"] = shcs(3, 10).align(screw)
    pen_front = p.pen_axis_d(pen_d) + pen_d / 2
    thumbscrew = get_handle(slide, "thumbscrew")
    items["pen"] = (
        cylinder(d=pen_d, h=PEN_LENGTH, fn=FN)
        .translate([p.pen_x, p.pen_axis_d(pen_d), FRAME.bed_top_z + lift])
        .color("Crimson")
    )
    items["thumbscrew"] = shcs(5, p.clamp_screw_len).align(
        shift_handle(thumbscrew, [0, pen_front + p.clamp_screw_len - thumbscrew[1][3], 0])
    )
    items["thumbscrew_nut"] = hex_nut(5).align(get_handle(slide, "thumbscrew_nut"))
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
