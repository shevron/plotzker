"""X idler slider (STATUS.md T3.16). Print ×1 (left gantry end).

Purpose: the U-shaped carrier of the X belt idler, riding on the dovetail ridge of
:mod:`x_idler_mount`. Both arms hold the M5 axle; an M3 screw through the mount's end block
pulls the slider outboard into a captive nut in its rear wall, tensioning the belt. It is
the generic :mod:`tension_idler` slider, sized with ``params.X_TENSIONER``.

Frame: left bracket-local, slider at mid-travel (:func:`x_idler_slider_installed`); the idler
axle at ``X_DRIVE.idler_x``.

Hardware: toothed idler (``IDLER``); 1 × M5×25 ISO 4762 (axle, head on the -y arm) + 1 × M5 nut
(pressed into the +y arm's outside); 1 × M3 nut (pressed in from the top of the rear wall).
Print: PETG or PLA; 0.2 mm; 4 perimeters; 40 % infill; dovetail lips down, arms up; no
supports, but the cavity roof bridges ~17 mm.
"""

from typing import TYPE_CHECKING

from plotter_cad.params import X_BELT, X_TENSIONER
from plotter_cad.parts.tension_idler import slider, slider_for_print
from plotter_cad.parts.x_idler_mount import BLOCK_X0

if TYPE_CHECKING:
    from pythonscad import Solid


def x_idler_slider_installed() -> Solid:
    """The slider in the left bracket-local frame, at mid-travel."""
    return slider(X_TENSIONER).translate([BLOCK_X0, X_BELT.y, 0])


def x_idler_slider() -> Solid:
    """Print orientation: dovetail lips on the bed."""
    return slider_for_print(X_TENSIONER)
