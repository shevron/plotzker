"""Assemblies: parts placed with hardware models for fit checks and renders.

Each assembly function returns a list of colored solids. :data:`ASSEMBLIES` maps a
render name (``renders/<name>.png``) to the function that builds it.
"""

from collections.abc import Callable

from plotter_cad.assemblies import carriage, gantry, hardware_gallery, skeleton

ASSEMBLIES: dict[str, Callable[[], list]] = {
    "carriage": carriage.carriage_fit_check,
    "gantry": gantry.gantry_fit_check,
    "hardware_gallery": hardware_gallery.hardware_gallery,
    "skeleton": skeleton.skeleton,
}
