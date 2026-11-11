"""Printable parts, one module per part, each modeled in its print orientation.

:data:`PRINTABLE_PARTS` maps each STL name (``stl/<name>.stl``) to the function that
builds it; the build CLI exports every entry.
"""

from collections.abc import Callable
from functools import partial

from plotter_cad.parts import (
    belt_clamp,
    gantry_end_bracket,
    x_carriage,
    x_endstop_mount,
    x_idler_mount,
    x_idler_spacer,
    x_motor_mount,
    y_idler_mount,
    y_motor_mount,
)

PRINTABLE_PARTS: dict[str, Callable[[], object]] = {
    "gantry_end_bracket_left": partial(
        gantry_end_bracket.gantry_end_bracket, gantry_end_bracket.Side.LEFT
    ),
    "gantry_end_bracket_right": partial(
        gantry_end_bracket.gantry_end_bracket, gantry_end_bracket.Side.RIGHT
    ),
    "belt_clamp": belt_clamp.belt_clamp,
    "x_carriage": x_carriage.x_carriage,
    "x_motor_mount": x_motor_mount.x_motor_mount,
    "x_idler_mount": x_idler_mount.x_idler_mount,
    "x_idler_spacer": x_idler_spacer.x_idler_spacer,
    "x_endstop_mount": x_endstop_mount.x_endstop_mount,
}
for _side in gantry_end_bracket.Side:
    PRINTABLE_PARTS[f"y_motor_mount_{_side.value}"] = partial(y_motor_mount.y_motor_mount, _side)
    PRINTABLE_PARTS[f"y_idler_mount_{_side.value}"] = partial(y_idler_mount.y_idler_mount, _side)
