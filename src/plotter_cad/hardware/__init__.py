"""Vendor-part dimensions and simple models (source of values: docs/hardware.md).

Each module defines frozen ``*Spec`` dataclasses with the dimensions, a module-level
instance (e.g. ``SK10``) and model functions (e.g. ``sk10()``). Models are for fit
checks and visuals only; holes for parts are built from the specs plus the
tolerances in :mod:`plotter_cad.params`. Values marked ``ASSUMED`` are catalog
numbers awaiting a measurement.
"""

from plotter_cad.hardware.bearings import B608, B623, B625, LM6UU, LM8UU, LM10UU, Bearing, bearing
from plotter_cad.hardware.belts import GT2, IDLER, PULLEY, gt2_belt, gt2_idler, gt2_pulley
from plotter_cad.hardware.endstop import ENDSTOP, endstop, endstop_placed
from plotter_cad.hardware.fasteners import M3, M3_INSERT, M5, hex_nut, metric, shcs, washer
from plotter_cad.hardware.linear_motion import SCS10UU, SK10, Y_SHAFT, scs10uu, sk10, y_shaft
from plotter_cad.hardware.motors import NEMA17, SG90, nema17, servo_sg90
from plotter_cad.hardware.vslot import (
    ECCENTRIC,
    VSLOT,
    VWHEEL,
    eccentric_spacer,
    vslot_x,
    vslot_y,
    vwheel,
)

__all__ = [
    "B608",
    "B623",
    "B625",
    "ECCENTRIC",
    "ENDSTOP",
    "GT2",
    "IDLER",
    "LM6UU",
    "LM8UU",
    "LM10UU",
    "M3",
    "M3_INSERT",
    "M5",
    "NEMA17",
    "PULLEY",
    "SCS10UU",
    "SG90",
    "SK10",
    "VSLOT",
    "VWHEEL",
    "Y_SHAFT",
    "Bearing",
    "bearing",
    "eccentric_spacer",
    "endstop",
    "endstop_placed",
    "gt2_belt",
    "gt2_idler",
    "gt2_pulley",
    "hex_nut",
    "metric",
    "nema17",
    "scs10uu",
    "servo_sg90",
    "shcs",
    "sk10",
    "vslot_x",
    "vslot_y",
    "vwheel",
    "washer",
    "y_shaft",
]  # fmt: skip
