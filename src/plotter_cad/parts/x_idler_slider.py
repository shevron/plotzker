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

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import (
    EPS,
    FN,
    handle,
    set_handles,
    teardrop_x,
    teardrop_y,
)
from plotter_cad.loads import X_BELT_LOADS
from plotter_cad.nut_slot import nut_slot
from plotter_cad.params import TOL, X_BELT, X_DRIVE, X_IDLER
from plotter_cad.part import DisplacementLimit, FemSpec, Force, LoadCase, Part, Support
from plotter_cad.regions import Box, Cylinder
from plotter_cad.types import Matrix

if TYPE_CHECKING:
    from pythonscad import Solid

X = X_IDLER
Y0 = X_BELT.y  #: the belt line (the slider's middle), bracket-local y
#: Idler axle: bolt head seat on the +y (rear) arm, shank toward -y
AXLE: Matrix = handle(
    [X_DRIVE.idler_x, Y0 + X.head_side * X.width / 2, X.axle_z], [X.axle_head_rot, 0, 0]
)


def _slider_local() -> Solid:
    """The slider with its rear face at x = 0 and its middle at y = 0 (bracket-local z)."""
    w, zb, top = X.width, X.z_bottom, X.arm_top
    arms = []
    for sy in (-1, 1):
        y0 = -(X.gap_y / 2 + X.arm_t) if sy < 0 else X.gap_y / 2
        arms.append(
            hull(
                cube([EPS, X.arm_t, top - zb]).translate([0, y0, zb]),
                cube([X.axle_x - X.arm_end_r, X.arm_t, EPS]).translate([0, y0, zb]),
                cylinder(d=2 * X.arm_end_r, h=X.arm_t, fn=FN)
                .rotate([-90, 0, 0])
                .translate([X.axle_x, y0, X.axle_z]),
            )
        )
    web = cube([X.web_t, w, top - zb]).translate([0, -w / 2, zb])
    body = web | arms[0] | arms[1]
    # printed on its back (+x up): the axle hole's teardrop and the nut slot's corner point +x
    axle_hole = (
        teardrop_y(TOL.bolt_hole_d(X.axle_m), w + 2)
        .rotate([0, 90, 0])
        .translate([X.axle_x, 0, X.axle_z])
    )
    axle_nut = (
        cylinder(d=TOL.nut_trap_ac(X.axle_m), h=TOL.nut_trap_h(X.axle_m) + 1, fn=6)
        .rotate([-90, 0, 0])
        .translate([X.axle_x, X.nut_y, X.axle_z])
    )
    screw_nut = nut_slot(X.screw_m, top - X.screw_z + 1, "x", "+z", X.nut_slot_extra).translate(
        [TOL.nut_wall + X.nut_t / 2, 0, X.screw_z]
    )
    # the screw's hole through the thrust wall and on into the blind tunnel for its tip
    # printed on its side the tunnel lies flat: a teardrop pointing up (-y in this frame)
    tunnel = (
        teardrop_x(TOL.bolt_hole_d(X.screw_m), X.tunnel_end + 1)
        .rotate([90, 0, 0])
        .translate([(X.tunnel_end - 1) / 2, 0, X.screw_z])
    )
    return body - axle_hole - axle_nut - screw_nut - tunnel


def x_idler_slider_installed() -> Solid:
    """The slider in the left bracket-local frame, at mid-travel."""
    return set_handles(_slider_local().translate([X.slider_x0, Y0, 0]), axle=AXLE)


def x_idler_slider() -> Solid:
    """Print orientation: lying on its side, the +y arm's outer face on the bed (the layers run
    along the arms, which carry the belt's pull)."""
    return _slider_local().rotate([-90, 0, 0]).translate([0, -X.z_bottom, X.width / 2])


# --- FEM definition -------------------------------------------------------------
_BORE_R = TOL.bolt_hole_d(X.axle_m) / 2 + 0.3
_AXLE_POINT = (X_DRIVE.idler_x, Y0, X.axle_z)
_BORE_LOAD = Cylinder(
    _AXLE_POINT, (0, 1, 0), _BORE_R, X.width / 2, facing=(-1, 0, 0), facing_tol_deg=60
)
_BORE = Cylinder(_AXLE_POINT, (0, 1, 0), _BORE_R, X.width / 2)
#: Where the screw nut bears on the thrust wall (the wall's face toward the idler)
_NUT_SEAT = Box(
    (X.slider_x0 + TOL.nut_wall - 0.3, Y0 - 3, X.screw_z - 3),
    (X.slider_x0 + TOL.nut_wall + 0.3, Y0 + 3, X.screw_z + 3),
    facing=(1, 0, 0),
)
#: The screw's hole and tunnel: the (stiff, steel) screw holds the slider sideways and vertically
_TUNNEL = Cylinder(
    (X.slider_x0 + X.tunnel_end / 2, Y0, X.screw_z),
    (1, 0, 0),
    TOL.bolt_hole_d(X.screw_m) / 2 + 0.3,
    X.tunnel_end / 2,
    inner_radius=TOL.bolt_hole_d(X.screw_m) / 2 - 0.3,
)
#: One outer face of the slider, standing for the tower's wall (stops the roll; no load)
_GUIDE = Box(
    (X.slider_x0, Y0 - X.width / 2 - 0.3, X.z_bottom),
    (X.slider_x0 + X.web_t, Y0 - X.width / 2 + 0.3, X.arm_top),
    facing=(0, -1, 0),
)


def _spec() -> FemSpec:
    """FEM spec of the slider."""
    cases = []
    for name, run_n, sustained in (
        ("belt_preload", X_BELT_LOADS.preload_n, True),
        ("belt_peak", X_BELT_LOADS.peak_n, False),
    ):
        cases.append(
            LoadCase(
                name,
                f"Two belt runs of {run_n:g} N pull the idler along the belt; the tension screw, "
                "in line with the axle, holds the slider: no couple",
                (Force(_BORE_LOAD, (2 * run_n, 0, 0), bearing=True),),
                "loads.X_BELT_LOADS",
                sustained=sustained,
            )
        )
    return FemSpec(
        load_cases=tuple(cases),
        supports=(
            Support(
                "screw_nut_seat",
                _NUT_SEAT,
                "Tension screw's nut seat: holds the slider along the belt",
                constrain=(True, False, False),
            ),
            Support(
                "screw_tunnel",
                _TUNNEL,
                "The screw in the thrust wall's hole and the tunnel: holds sideways and vertically",
                constrain=(False, True, True),
            ),
            Support(
                "guide_wall",
                _GUIDE,
                "Tower wall beside the slider: stops the roll (no load)",
                constrain=(False, True, False),
            ),
        ),
        displacement_limits=(
            DisplacementLimit("idler_axle_along_belt", _BORE, 0.3, (1, 0, 0)),
            DisplacementLimit("idler_axle_sideways", _BORE, 0.1, (0, 1, 0)),
            DisplacementLimit("idler_axle_vertical", _BORE, 0.1, (0, 0, 1)),
        ),
    )


PART = Part(
    name="x_idler_slider",
    description="X idler slider: floating U-shaped carrier of the idler axle, tied to the tower",
    build=x_idler_slider_installed,
    frame="installed",
    build_direction=(0, -1, 0),
    fem=_spec(),
)
