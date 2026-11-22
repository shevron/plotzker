"""Y idler slider (STATUS.md T3.17, T3.23). Print ×1 left + ×1 right (mirror images).

Purpose: the U-shaped carrier of the Y belt idler. It floats: no rail, held only by an M3 tension
screw along the belt line at the axle's height, through the tower of :mod:`y_idler_mount`. The
screw's head is on the tower plate's front face; a captive nut at the rear of the slider's wall
pulls the slider forward (−y), tensioning the belt, and a blind tunnel in the wall takes the
screw's tip. It is the generic :mod:`floating_idler` slider, sized with ``params.Y_IDLER``.

Frame: left side frame, slider at mid-travel (:func:`y_idler_slider_installed`): the axle bolt's
head is on the inboard arm, its nut in the outboard arm. The right-hand slider is the mirror
image; :func:`y_idler_slider` returns each in print orientation.

Hardware: toothed idler (``IDLER``); 1 × M5×25 ISO 4762 (axle) + 1 × M5 nut (pressed into the
outboard arm's outside); 1 × M3 nut (pressed in from the top of the rear wall).
Print: default profile (``profiles/default.toml``); upside down, the flat top on the bed (the build
direction is -z, so the layers lie in the horizontal plane, parallel to the belt's pull and to the
tightening of the axle nut and the tension screw); no supports.

FEM: see :func:`plotter_cad.parts.floating_idler.slider_fem`; the right slider is the exact mirror
image, so the left one's check applies.
"""

from typing import TYPE_CHECKING

from plotter_cad.loads import Y_BELT_LOADS
from plotter_cad.params import Y_AXIS, Y_DRIVE, Y_IDLER
from plotter_cad.part import Part
from plotter_cad.parts.floating_idler import slider_fem, slider_for_print, slider_local
from plotter_cad.parts.y_idler_mount import to_side_frame
from plotter_cad.regions import Placement
from plotter_cad.types import Side

if TYPE_CHECKING:
    from pythonscad import Solid


def y_idler_slider_installed() -> Solid:
    """The (left) slider in the left side frame, at mid-travel."""
    return to_side_frame(slider_local(Y_IDLER).translate([Y_IDLER.rear_mid, 0, 0]))


def y_idler_slider(side: Side = Side.LEFT) -> Solid:
    """The slider for one side in print orientation: upside down (the right one is the
    mirror image: its axle nut is on the other arm)."""
    part = slider_for_print(Y_IDLER)
    return part.mirror([0, 1, 0]) if side is Side.RIGHT else part


# --- FEM definition -------------------------------------------------------------
#: The tensioner's frame in the left side frame (slide direction +y)
PLACEMENT = Placement(1, (Y_AXIS.belt_x, Y_DRIVE.idler_block_y, 0.0))

PART_LEFT = Part(
    name="y_idler_slider_left",
    description="Y idler slider (left): floating carrier of the idler axle, tied to the tower",
    build=y_idler_slider_installed,
    frame="installed",
    build_direction=(0, 0, -1),
    fem=slider_fem(Y_IDLER, PLACEMENT, Y_BELT_LOADS, "loads.Y_BELT_LOADS"),
)
PART_RIGHT = Part(
    name="y_idler_slider_right",
    description="Y idler slider (right): mirror image of the left one",
    build=lambda: y_idler_slider_installed().mirror([1, 0, 0]),
    frame="installed",
    build_direction=(0, 0, -1),
    mirror_of="y_idler_slider_left",
)
