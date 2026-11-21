"""X idler slider (STATUS.md T3.16, T3.22). Print ×1 (left gantry end).

Purpose: the U-shaped carrier of the X belt idler. Both arms hold the M5 axle. It floats: no rail,
held only by an M3 tension screw that runs along the belt line at the axle's height, through the
tower of the left gantry bracket (:mod:`gantry_end_bracket`). The screw's head sits on the tower's
outer face (hex key from outside); a captive nut at the rear of the slider's wall pulls the slider
toward the tower, away from the belt, and a blind tunnel in the wall takes the screw's tip as the
slider moves. The belt's pull and the screw's are one line, so nothing twists the slider; the
tower's two side walls only keep it from rolling while the screw is turned.

  side view (arms cut away at the axle)         top view
                                                ┌──────────────────────┐
   tower   ┌────────┐   ◯ idler / axle (M5)     │ web ═arm═════◯       │
  ┌──┐     │▓ nut   │ ┌─┴──┐                    │ ▓  ═arm═════         │
  │▓▓├─────┼▓▓▓▓▓▓▓▶ tunnel                     └──────────────────────┘
  └──┘     └────────┘

Frame: left bracket-local, slider at mid-travel (:func:`x_idler_slider_installed`); the idler
axle at ``X_DRIVE.idler_x``.

Hardware: toothed idler (``IDLER``); 1 × M5×25 ISO 4762 (axle, head on the +y arm) + 1 × M5 nut
(pressed into the -y arm's outside); 1 × M3 nut (pressed in from the top of the wall) + 1 ×
M3×``X_IDLER.screw_len`` ISO 4762 (tension screw, from the tower's outer face).
Print: default profile (``profiles/default.toml``); lying on its side, the +y arm's outer face on
the bed (the build direction is -y in the installed frame, so the layers run along the arms that
carry the belt's pull); no supports; the tunnel is a teardrop lying flat, closed by a 1.6 mm wall.

FEM: the belt pulls the axle bore inboard; the M3 nut's seat holds it in x; the screw holds it
sideways and vertically in the tunnel and one outer face stands for the tower's wall (roll);
see :data:`PART`.
"""

from typing import TYPE_CHECKING

from plotter_cad.geometry import handle, set_handles
from plotter_cad.loads import X_BELT_LOADS
from plotter_cad.params import X_IDLER
from plotter_cad.part import Part
from plotter_cad.parts.floating_idler import slider_fem, slider_for_print, slider_local
from plotter_cad.regions import Placement
from plotter_cad.types import Matrix

if TYPE_CHECKING:
    from pythonscad import Solid

X = X_IDLER
#: Idler axle: bolt head seat on the +y (rear) arm, shank toward -y
AXLE: Matrix = handle(
    [X.axle_pos, X.belt_pos + X.head_side * X.width / 2, X.axle_z], [X.axle_head_rot, 0, 0]
)
#: The tensioner frame in the left bracket-local frame (tower's outer face, belt line)
PLACEMENT = Placement(0, (X.tower_s0, X.belt_pos, 0.0))


def x_idler_slider_installed() -> Solid:
    """The slider in the left bracket-local frame, at mid-travel."""
    return set_handles(slider_local(X).translate([X.slider_s0, X.belt_pos, 0]), axle=AXLE)


def x_idler_slider() -> Solid:
    """Print orientation: lying on its side, the +y arm's outer face on the bed."""
    return slider_for_print(X)


PART = Part(
    name="x_idler_slider",
    description="X idler slider: floating U-shaped carrier of the idler axle, tied to the tower",
    build=x_idler_slider_installed,
    frame="installed",
    build_direction=(0, -X.head_side, 0),
    fem=slider_fem(X, PLACEMENT, X_BELT_LOADS, "loads.X_BELT_LOADS"),
)
