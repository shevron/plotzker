"""The idler slider (STATUS.md T3.16, T3.22, T3.23, T3.26). Print ×3: one for the X idler and
one for each Y idler, all the same part.

Purpose: the U-shaped carrier of a belt idler. Both arms hold the M5 axle. It floats: no rail,
held only by an M3 tension screw that runs along the belt line at the axle's height, through the
tower of its mount (the left gantry bracket for X, the idler mounts for Y). The screw's head sits
on the tower's outer face (hex key from outside); a captive nut at the rear of the slider's wall
pulls the slider toward the tower, away from the belt, and a blind tunnel in the wall takes the
screw's tip as the slider moves. The belt's pull and the screw's are one line, so nothing twists
the slider; the tower's two side walls only keep it from rolling while the screw is turned.

  side view (arms cut away at the axle)         top view
                                                ┌──────────────────────┐
   tower   ┌────────┐   ◯ idler / axle (M5)     │ web ═arm═════◯       │
  ┌──┐     │▓ nut   │ ┌─┴──┐                    │ ▓  ═arm═════         │
  │▓▓├─────┼▓▓▓▓▓▓▓▶ tunnel                     └──────────────────────┘
  └──┘     └────────┘

One shape for all three: ``params.X_IDLER`` and ``Y_IDLER`` differ only in where they are, and
the axle bolt's head is on the same arm (``head_side`` +1) in every one. The right Y mount is the
left one's mirror image except that its tower's head pocket is on the other wall (see
:func:`plotzker.parts.y_idler_mount.idler_for`), so the same unmirrored slider fits both.

Frame: the left bracket's local frame, slider at mid-travel (:func:`x_idler_slider_installed`);
the idler axle at ``X_DRIVE.idler_x``. The Y sliders are placed in the side frame by
:func:`y_idler_slider_installed`.

Hardware: toothed idler (``IDLER_SPEC``); 1 × M5×25 ISO 4762 (axle, head on the +y arm) + 1 × M5 nut
(pressed into the -y arm's outside); 1 × M3 nut (pressed in from the top of the wall) + 1 ×
M3×``X_IDLER.screw_len`` ISO 4762 (tension screw, from the tower's outer face).
Print: default profile (``profiles/default.toml``); upside down, the flat top on the bed (the
build direction is -z, so the layers lie in the xy plane, parallel to the belt's pull and to the
tightening of the axle nut and the tension screw); no supports; the holes along x and y are
teardrops pointing up, the tunnel is closed by a 1.6 mm wall.

FEM: the belt pulls the axle bore inboard; the M3 nut's seat holds it in x; the screw holds it
sideways and vertically in the tunnel and one outer face stands for the tower's wall (roll);
see :data:`PART`. It is checked in the X idler's frame; the Y idlers carry the same belt load.
"""

from typing import TYPE_CHECKING

from cadder.handles import handle, set_handles
from cadder.part import PrintedPart
from cadder.regions import Placement
from cadder.types import Matrix

from plotzker.loads import X_BELT_LOADS
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import X_IDLER
from plotzker.parts.floating_idler import slider_fem, slider_for_print, slider_local
from plotzker.parts.y_idler_mount import idler_for, to_side_frame
from plotzker.types import Side

if TYPE_CHECKING:
    from pythonscad import Solid

X = X_IDLER
#: Idler axle: bolt head seat on the +y (rear) arm, shank toward -y
AXLE: Matrix = handle([X.axle_pos, X.belt_pos + X.head_side * X.width / 2, X.axle_z], [X.axle_head_rot, 0, 0])
#: The tensioner frame in the left bracket-local frame (tower's outer face, belt line)
PLACEMENT = Placement(0, (X.tower_s0, X.belt_pos, 0.0))


def x_idler_slider_installed() -> Solid:
    """The slider in the left bracket-local frame, at mid-travel."""
    return set_handles(slider_local(X).translate([X.slider_s0, X.belt_pos, 0]), axle=AXLE)


def y_idler_slider_installed(side: Side = Side.LEFT) -> Solid:
    """The slider in the left side frame at mid-travel (the right one is the left frame's
    mirror image like the rest of the right side, so its head is on the other arm there)."""
    t = idler_for(side)
    return to_side_frame(slider_local(t).translate([t.rear_mid, 0, 0]))


def idler_slider() -> Solid:
    """Print orientation: upside down, the top on the bed."""
    return slider_for_print(X)


PART = PrintedPart(
    name="idler_slider",
    description="Idler slider (×3: X and both Y): floating U-shaped carrier of the idler axle",
    build=idler_slider,
    analysis=x_idler_slider_installed,
    frame="installed",
    build_direction=(0, 0, -1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=slider_fem(X, PLACEMENT, X_BELT_LOADS, "loads.X_BELT_LOADS"),
)
