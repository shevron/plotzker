"""Plotter-specific hardware: the endstop board, the ZRIB controller board, the Y shafts and
the 24 V supply with its mains inlet and DC connector.

Generic vendor parts (fasteners, bearings, belts, motors, V-slot, SK10...) come from
:mod:`cadder.hardware`. Source of values: docs/hardware.md.
"""

from typing import TYPE_CHECKING

from cadder.hardware import Shaft, shaft

from plotzker.hardware.endstop import ENDSTOP, endstop, endstop_keepout, endstop_placed
from plotzker.hardware.psu import C14_INLET, PSU, XT60, c14_inlet, psu, xt60_female
from plotzker.hardware.zrib import ZRIB, zrib

if TYPE_CHECKING:
    from pythonscad import Solid

#: The two Ø10 Y shafts, cut to 700 mm
Y_SHAFT = Shaft(length=700)


def y_shaft(length: float = Y_SHAFT.length) -> Solid:
    """Ø10 Y shaft. Origin: start of the shaft on its axis; runs along +Y."""
    return shaft(Y_SHAFT, length)


__all__ = [
    "C14_INLET",
    "ENDSTOP",
    "PSU",
    "XT60",
    "Y_SHAFT",
    "ZRIB",
    "c14_inlet",
    "endstop",
    "endstop_keepout",
    "endstop_placed",
    "psu",
    "xt60_female",
    "y_shaft",
    "zrib",
]
