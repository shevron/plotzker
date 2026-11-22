"""Vendor-part dimensions and simple models (source of values: docs/hardware.md).

Each module defines frozen ``*Spec`` dataclasses with the dimensions, a module-level
instance (e.g. ``SK10``) and model functions (e.g. ``sk10()``). Models are for fit
checks and visuals only; holes for parts are built from the specs plus the
tolerances in :mod:`plotzker.params`. Values marked ``ASSUMED`` are catalog
numbers awaiting a measurement.
"""

from plotzker.hardware.bearings import B608, B623, B625, LM6UU, LM8UU, LM10UU, Bearing, bearing
from plotzker.hardware.belts import GT2, IDLER, PULLEY, gt2_belt, gt2_idler, gt2_pulley
from plotzker.hardware.endstop import (
    ENDSTOP,
    endstop,
    endstop_keepout,
    endstop_placed,
    place_in_frame,
)
from plotzker.hardware.fasteners import (
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
from plotzker.hardware.linear_motion import SCS10UU, SK10, Y_SHAFT, scs10uu, sk10, y_shaft
from plotzker.hardware.motors import FT90M, NEMA17, nema17, servo_ft90m, servo_horn
from plotzker.hardware.vslot import (
    ECCENTRIC,
    VSLOT,
    VWHEEL,
    eccentric_spacer,
    vslot_x,
    vslot_y,
    vwheel,
)
from plotzker.hardware.zrib import ZRIB, zrib

__all__ = [
    "B608",
    "B623",
    "B625",
    "ECCENTRIC",
    "ENDSTOP",
    "FT90M",
    "GT2",
    "IDLER",
    "LM6UU",
    "LM8UU",
    "LM10UU",
    "M3",
    "M5",
    "NEMA17",
    "PULLEY",
    "SCS10UU",
    "SK10",
    "VSLOT",
    "VWHEEL",
    "Y_SHAFT",
    "ZRIB",
    "Bearing",
    "bearing",
    "countersunk_screw",
    "eccentric_spacer",
    "endstop",
    "endstop_keepout",
    "endstop_placed",
    "gt2_belt",
    "gt2_idler",
    "gt2_pulley",
    "hex_nut",
    "metric",
    "nema17",
    "place_in_frame",
    "scs10uu",
    "servo_ft90m",
    "servo_horn",
    "shcs",
    "sk10",
    "spring",
    "t_nut",
    "vslot_x",
    "vslot_y",
    "vwheel",
    "washer",
    "y_shaft",
    "zrib",
]  # fmt: skip
