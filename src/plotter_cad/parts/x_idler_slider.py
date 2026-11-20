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
from plotter_cad.params import TOL, X_BELT, X_DRIVE, X_TENSIONER
from plotter_cad.part import DisplacementLimit, FemSpec, Force, LoadCase, Part, Support
from plotter_cad.parts.tension_idler import slider, slider_for_print, slider_x0
from plotter_cad.parts.x_idler_mount import BLOCK_X0
from plotter_cad.regions import Box, Cylinder

if TYPE_CHECKING:
    from pythonscad import Solid


def x_idler_slider_installed() -> Solid:
    """The slider in the left bracket-local frame, at mid-travel."""
    return slider(X_TENSIONER).translate([BLOCK_X0, X_BELT.y, 0])


def x_idler_slider() -> Solid:
    """Print orientation: lying on its back."""
    return slider_for_print(X_TENSIONER)


# --- FEM definition -------------------------------------------------------------
T = X_TENSIONER
_X0 = BLOCK_X0 + slider_x0(T)  #: slider's rear face (left bracket-local x)
_AXLE = (X_DRIVE.idler_x, X_BELT.y, T.axle_z)
_BORE_R = TOL.bolt_hole_d(T.axle_m) / 2 + 0.3
#: The axle bore's wall pushed by the axle (the belt pulls toward +x, so the faces facing -x)
AXLE_BORE_LOAD = Cylinder(
    center=_AXLE,
    axis=(0, 1, 0),
    radius=_BORE_R,
    half_length=T.width / 2,
    facing=(-1, 0, 0),
    facing_tol_deg=60,
)
#: The whole axle bore (the idler's position)
AXLE_BORE = Cylinder(center=_AXLE, axis=(0, 1, 0), radius=_BORE_R, half_length=T.width / 2)
#: Where the tension screw's nut bears on the rear wall (the wall pulled toward -x)
NUT_SEAT = Box(
    lo=(_X0 + TOL.nut_wall - 0.3, X_BELT.y - 3, T.screw_z - 3),
    hi=(_X0 + TOL.nut_wall + 0.3, X_BELT.y + 3, T.screw_z + 3),
    facing=(1, 0, 0),
)
_CHANNEL_HALF_W = T.ridge_neck / 2 + T.ridge_h + T.slide_gap * 2**0.5 + 0.5
#: The dovetail channel's flanks and roof, riding on the rail's ridge
DOVETAIL = Box(
    lo=(_X0, X_BELT.y - _CHANNEL_HALF_W, T.slider_z0 + 0.3),
    hi=(_X0 + T.plate_len, X_BELT.y + _CHANNEL_HALF_W, T.slider_z0 + T.ridge_h + T.slide_gap + 0.1),
)


def _belt_case(name: str, run_n: float, sustained: bool) -> LoadCase:
    """The belt's pull on the idler axle (two runs)."""
    return LoadCase(
        name=name,
        description=f"Two belt runs of {run_n:g} N pull the idler axle inboard (+x)",
        loads=(Force(AXLE_BORE_LOAD, (2 * run_n, 0, 0)),),
        source="loads.X_BELT_LOADS",
        sustained=sustained,
    )


PART = Part(
    name="x_idler_slider",
    description="X idler slider: U-shaped carrier of the idler axle, on the mount's dovetail",
    build=x_idler_slider_installed,
    frame="installed",
    build_direction=(1, 0, 0),
    fem=FemSpec(
        load_cases=(
            _belt_case("belt_preload", X_BELT_LOADS.preload_n, sustained=True),
            _belt_case("belt_peak", X_BELT_LOADS.peak_n, sustained=False),
        ),
        supports=(
            Support(
                "screw_nut_seat",
                NUT_SEAT,
                "Tension screw's nut seat: holds the slider in x",
                constrain=(True, False, False),
            ),
            Support(
                "dovetail",
                DOVETAIL,
                "Dovetail channel on the ridge: holds y and z, free to slide in x",
                constrain=(False, True, True),
            ),
        ),
        displacement_limits=(
            DisplacementLimit("idler_axle_along_belt", AXLE_BORE, 0.3, (1, 0, 0)),
            DisplacementLimit("idler_axle_sideways", AXLE_BORE, 0.1, (0, 1, 0)),
            DisplacementLimit("idler_axle_vertical", AXLE_BORE, 0.1, (0, 0, 1)),
        ),
    ),
)
