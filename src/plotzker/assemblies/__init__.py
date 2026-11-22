"""Assemblies: parts placed with hardware models for fit checks and renders.

Each assembly function returns a list of colored solids. :data:`ASSEMBLIES` maps a
render name (``renders/<name>.png``) to the function that builds it.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from plotzker.assemblies import (
    carriage,
    gantry,
    hardware_gallery,
    machine,
    pen_holder,
    skeleton,
    tension_idler,
    y_drive,
    zrib_mount,
)
from plotzker.types import Side

if TYPE_CHECKING:
    from pythonscad import Solid

ASSEMBLIES: dict[str, Callable[[], list[Solid]]] = {
    "carriage": carriage.carriage_fit_check,
    "gantry": gantry.gantry_fit_check,
    "gantry_end_left": lambda: gantry.gantry_end_local(Side.LEFT),  # idler, endstop (close-up)
    "gantry_end_right": lambda: gantry.gantry_end_local(Side.RIGHT),  # motor (close-up)
    "hardware_gallery": hardware_gallery.hardware_gallery,
    "machine": machine.machine,
    "pen_holder": pen_holder.pen_holder_fit_check,
    "skeleton": skeleton.skeleton,
    "tension_idler_fit": tension_idler.tension_idler_fit_check,
    "y_drive": y_drive.y_drive_fit_check,
    "zrib_mount": zrib_mount.zrib_mount_fit_check,
}
