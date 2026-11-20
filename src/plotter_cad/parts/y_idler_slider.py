"""Y idler slider (STATUS.md T3.17). Print ×1 left + ×1 right (mirror images).

Purpose: the U-shaped carrier of the Y belt idler, riding on the dovetail ridge of
:mod:`y_idler_mount`. Both arms hold the M5 axle; an M3 screw through the mount's end block
pulls the slider forward (−y) into a captive nut in its rear wall, tensioning the belt. It is
the generic :mod:`tension_idler` slider, sized with ``params.Y_TENSIONER`` (thinner plate: the
idler is low).

Frame: left side frame, slider at mid-travel (:func:`y_idler_slider_installed`): the axle bolt's
head is on the inboard arm, its nut in the outboard arm. The right-hand slider is the mirror
image; :func:`y_idler_slider` returns each in print orientation.

Hardware: toothed idler (``IDLER``); 1 × M5×25 ISO 4762 (axle) + 1 × M5 nut (pressed into the
outboard arm's outside); 1 × M3 nut (pressed in from the top of the rear wall).
Print: default profile (``profiles/default.toml``); lying on its back (rear wall on the bed,
dovetail vertical; the build direction is +y in the left side frame); no supports, no bridges.

FEM: see :func:`plotter_cad.parts.tension_idler.slider_fem`; the right slider is the exact mirror
image, so the left one's check applies.
"""

from typing import TYPE_CHECKING

from plotter_cad.loads import Y_BELT_LOADS
from plotter_cad.params import Y_AXIS, Y_DRIVE, Y_TENSIONER
from plotter_cad.part import Part
from plotter_cad.parts.tension_idler import slider, slider_fem, slider_for_print
from plotter_cad.parts.y_idler_mount import to_side_frame
from plotter_cad.regions import Placement
from plotter_cad.types import Side

if TYPE_CHECKING:
    from pythonscad import Solid


def y_idler_slider_installed() -> Solid:
    """The (left) slider in the left side frame, at mid-travel."""
    return to_side_frame(slider(Y_TENSIONER))


def y_idler_slider(side: Side = Side.LEFT) -> Solid:
    """The slider for one side in print orientation: lying on its back (the right one is
    the mirror image: its axle nut is on the other arm)."""
    part = slider_for_print(Y_TENSIONER)
    return part.mirror([0, 1, 0]) if side is Side.RIGHT else part


# --- FEM definition -------------------------------------------------------------
#: The tensioner's frame in the left side frame (slide direction +y)
PLACEMENT = Placement(1, (Y_AXIS.belt_x, Y_DRIVE.idler_block_y, 0.0))

PART_LEFT = Part(
    name="y_idler_slider_left",
    description="Y idler slider (left): carrier of the idler axle, on the mount's dovetail",
    build=y_idler_slider_installed,
    frame="installed",
    build_direction=(0, 1, 0),
    fem=slider_fem(Y_TENSIONER, PLACEMENT, Y_BELT_LOADS, "loads.Y_BELT_LOADS"),
)
PART_RIGHT = Part(
    name="y_idler_slider_right",
    description="Y idler slider (right): mirror image of the left one",
    build=lambda: y_idler_slider_installed().mirror([1, 0, 0]),
    frame="installed",
    build_direction=(0, 1, 0),
    mirror_of="y_idler_slider_left",
)
