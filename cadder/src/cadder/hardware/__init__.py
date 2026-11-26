"""Vendor-part dimensions and simple models: fasteners, bearings, belts, motors, V-slot,
linear motion.

Each module defines frozen ``*Spec`` dataclasses with the dimensions, a module-level instance
(e.g. ``SK10_SPEC``) and model functions (e.g. ``sk10()``). Models are for fit checks and visuals
only; holes for parts are built from the specs plus the project's print tolerances
(:class:`cadder.printing.Tolerances`). Values marked ``ASSUMED`` are catalog numbers awaiting
a measurement.
"""

from cadder.hardware.bearings import B608, B623, B625, LM6UU, LM8UU, LM10UU, Bearing, bearing
from cadder.hardware.belts import GT2_SPEC, IDLER_SPEC, PULLEY_SPEC, gt2_belt, gt2_idler, gt2_pulley
from cadder.hardware.fasteners import (
    M3,
    M5,
    countersunk_screw,
    hex_nut,
    metric,
    shcs,
    spring,
    t_nut,
    washer,
)
from cadder.hardware.linear_motion import SCS10UU_SPEC, SK10_SPEC, Shaft, scs10uu, shaft, sk10
from cadder.hardware.motors import FT90M_SPEC, NEMA17_SPEC, nema17, servo_ft90m, servo_horn
from cadder.hardware.vslot import (
    ECCENTRIC_SPEC,
    VSLOT_SPEC,
    VWHEEL_SPEC,
    eccentric_spacer,
    vslot_x,
    vslot_y,
    vwheel,
)

__all__ = [
    "B608",
    "B623",
    "B625",
    "ECCENTRIC_SPEC",
    "FT90M_SPEC",
    "GT2_SPEC",
    "IDLER_SPEC",
    "LM6UU",
    "LM8UU",
    "LM10UU",
    "M3",
    "M5",
    "NEMA17_SPEC",
    "PULLEY_SPEC",
    "SCS10UU_SPEC",
    "SK10_SPEC",
    "VSLOT_SPEC",
    "VWHEEL_SPEC",
    "Bearing",
    "Shaft",
    "bearing",
    "countersunk_screw",
    "eccentric_spacer",
    "gt2_belt",
    "gt2_idler",
    "gt2_pulley",
    "hex_nut",
    "metric",
    "nema17",
    "scs10uu",
    "servo_ft90m",
    "servo_horn",
    "shaft",
    "shcs",
    "sk10",
    "spring",
    "t_nut",
    "vslot_x",
    "vslot_y",
    "vwheel",
    "washer",
]  # fmt: skip
