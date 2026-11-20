"""X idler slider (STATUS.md T3.16). Print ×1 (left gantry end).

Purpose: the U-shaped carrier of the X belt idler, riding on the dovetail ridge of
:mod:`x_idler_mount`. Both arms hold the M5 axle; an M3 screw through the mount's end block
pulls the slider outboard into a captive nut in its rear wall, tensioning the belt. It is
the generic :mod:`tension_idler` slider, sized with ``params.X_TENSIONER``.

Frame: left bracket-local, slider at mid-travel (:func:`x_idler_slider_installed`); the idler
axle at ``X_DRIVE.idler_x``.

Hardware: toothed idler (``IDLER``); 1 × M5×25 ISO 4762 (axle, head on the -y arm) + 1 × M5 nut
(pressed into the +y arm's outside); 1 × M3 nut (pressed in from the top of the rear wall).
Print: default profile (``profiles/default.toml``); lying on its back (rear wall on the bed,
dovetail vertical, so the build direction is +x in the installed frame); no supports, no bridges.

FEM: the belt pulls the axle bore inboard; the M3 nut's seat in the rear wall holds it in x and
the dovetail channel in y and z; see :data:`PART`.
"""

from typing import TYPE_CHECKING

from plotter_cad.loads import X_BELT_LOADS
from plotter_cad.params import X_BELT, X_TENSIONER
from plotter_cad.part import Part
from plotter_cad.parts.tension_idler import slider, slider_fem, slider_for_print
from plotter_cad.parts.x_idler_mount import BLOCK_X0
from plotter_cad.regions import Placement

if TYPE_CHECKING:
    from pythonscad import Solid


def x_idler_slider_installed() -> Solid:
    """The slider in the left bracket-local frame, at mid-travel."""
    return slider(X_TENSIONER).translate([BLOCK_X0, X_BELT.y, 0])


def x_idler_slider() -> Solid:
    """Print orientation: lying on its back."""
    return slider_for_print(X_TENSIONER)


# --- FEM definition -------------------------------------------------------------
#: The tensioner's frame in the left bracket-local frame (block outer face, belt line)
PLACEMENT = Placement(0, (BLOCK_X0, X_BELT.y, 0.0))

PART = Part(
    name="x_idler_slider",
    description="X idler slider: U-shaped carrier of the idler axle, on the mount's dovetail",
    build=x_idler_slider_installed,
    frame="installed",
    build_direction=(1, 0, 0),
    fem=slider_fem(X_TENSIONER, PLACEMENT, X_BELT_LOADS, "loads.X_BELT_LOADS"),
)
