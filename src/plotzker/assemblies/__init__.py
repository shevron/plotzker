"""Assemblies: parts placed with hardware models for fit checks and renders.

Each assembly function returns a list of colored solids. :data:`ASSEMBLIES` maps a
render name (``renders/<name>.png``) to its :class:`~cadder.assembly.Assembly`.
"""

from cadder.assembly import Assembly

from plotzker.assemblies import (
    carriage,
    gantry,
    hardware_gallery,
    machine,
    pen_holder,
    psu_mount,
    skeleton,
    y_drive,
)
from plotzker.types import Side

ASSEMBLIES: dict[str, Assembly] = {
    a.name: a
    for a in (
        Assembly(
            name="carriage",
            description="The carriage assembly on a 240 mm piece of the beam",
            build=carriage.carriage_fit_check,
        ),
        Assembly(
            name="gantry",
            description="The gantry at mid-board on 400 mm stubs of the Y shafts",
            build=gantry.gantry_fit_check,
        ),
        Assembly(
            name="gantry_end_left",
            description="Close-up of the left gantry end: X idler and endstop",
            build=lambda: gantry.gantry_end_local(Side.LEFT),
        ),
        Assembly(
            name="gantry_end_right",
            description="Close-up of the right gantry end: X motor",
            build=lambda: gantry.gantry_end_local(Side.RIGHT),
        ),
        Assembly(
            name="hardware_gallery",
            description="All vendor-part models laid out in rows for a visual check",
            build=hardware_gallery.hardware_gallery,
        ),
        Assembly(
            name="machine",
            description="The machine at mid-travel, pen up",
            build=machine.machine,
        ),
        Assembly(
            name="pen_holder",
            description="The carriage with its pen holder on a piece of the beam, pen up",
            build=pen_holder.pen_holder_fit_check,
        ),
        Assembly(
            name="psu_mount",
            description="The PSU on its brackets beside a piece of the baseboard, hood and inlet",
            build=psu_mount.psu_mount_fit_check,
        ),
        Assembly(
            name="skeleton",
            description="Frame, Y axis, gantry and carriage",
            build=skeleton.skeleton,
        ),
        Assembly(
            name="y_drive",
            description="Baseboard, shafts, SK10s, gantry and both Y drives",
            build=y_drive.y_drive_fit_check,
        ),
    )
}
