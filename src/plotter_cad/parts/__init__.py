"""Printable parts, one module per part, each modeled in its print orientation.

:data:`PRINTABLE_PARTS` maps each STL name (``stl/<name>.stl``) to the function that
builds it; the build CLI exports every entry. :data:`PARTS` holds the parts that are defined as
:class:`~plotter_cad.part.Part` (print profile, material, FEM specification); parts are moved
over one at a time (``docs/fem-subagent-plan.md``).
"""

from collections.abc import Callable
from functools import partial

from plotter_cad.part import Part
from plotter_cad.parts import (
    belt_clamp,
    gantry_end_bracket,
    loom_anchor,
    loom_rail,
    pen_holder_body,
    pen_slide,
    tension_idler,
    x_carriage,
    x_idler_mount,
    x_idler_slider,
    x_motor_mount,
    y_idler_mount,
    y_idler_slider,
    y_motor_mount,
    zrib_guard,
    zrib_hanger,
)
from plotter_cad.types import Side

PRINTABLE_PARTS: dict[str, Callable[[], object]] = {
    "gantry_end_bracket_left": partial(gantry_end_bracket.gantry_end_bracket, Side.LEFT),
    "gantry_end_bracket_right": partial(gantry_end_bracket.gantry_end_bracket, Side.RIGHT),
    "belt_clamp": belt_clamp.belt_clamp,
    "loom_anchor": loom_anchor.loom_anchor,
    "loom_rail": loom_rail.loom_rail,
    "pen_holder_body": pen_holder_body.pen_holder_body,
    "pen_slide": pen_slide.pen_slide,
    "tension_idler_rail": tension_idler.tension_idler_rail,
    "tension_idler_slider": tension_idler.tension_idler_slider,
    "x_carriage": x_carriage.x_carriage,
    "zrib_hanger": zrib_hanger.zrib_hanger,
    "zrib_guard": zrib_guard.zrib_guard,
    "x_motor_mount": x_motor_mount.x_motor_mount,
    "x_idler_mount": x_idler_mount.x_idler_mount,
    "x_idler_slider": x_idler_slider.x_idler_slider,
}
for _side in Side:
    PRINTABLE_PARTS[f"y_motor_mount_{_side.value}"] = partial(y_motor_mount.y_motor_mount, _side)
    PRINTABLE_PARTS[f"y_idler_mount_{_side.value}"] = partial(y_idler_mount.y_idler_mount, _side)
    PRINTABLE_PARTS[f"y_idler_slider_{_side.value}"] = partial(y_idler_slider.y_idler_slider, _side)

PARTS: dict[str, Part] = {
    part.name: part
    for part in (
        gantry_end_bracket.PART_LEFT,
        gantry_end_bracket.PART_RIGHT,
        x_idler_mount.PART,
        x_idler_slider.PART,
        x_carriage.PART,
        pen_slide.PART,
        pen_holder_body.PART,
        x_motor_mount.PART,
        y_idler_mount.PART_LEFT,
        y_idler_mount.PART_RIGHT,
        y_motor_mount.PART_LEFT,
        y_motor_mount.PART_RIGHT,
        y_idler_slider.PART_LEFT,
        y_idler_slider.PART_RIGHT,
    )
}
