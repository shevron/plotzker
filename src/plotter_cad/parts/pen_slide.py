"""Pen slide: the moving half of the v1 tool head (STATUS.md T3.6). Print ×1.

Purpose: carries the pen. It hangs on the Ø6 rod through two printed sleeves (relief between
them), holds the pen in a 90° V-block closed by a yoke and an M5 thumbscrew, and has a lug
with a vertical slot for the servo horn's pin and a groove for the body's key rib. The
slide's weight (plus the pen) sets the pen pressure; the pin lifts the slot's ceiling.

  top view (looking down, carriage at the bottom)       pen Ø7…16 axis 16…22 mm out
                                                            ╲   ╱  ← V-block (90°)
      lug + slot       sleeve column                         ◯ pen
      ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒◯▒▒▒▒▒▒▒▒                       ┃   ┃ yoke arms
      ▔▔▔▔▔▔▔▔ back face (touches nothing; 0.6 mm from the plate)  ━━━ thumbscrew bar

Frame: the head frame of ``params.PenHolder``; :func:`pen_slide_head` returns the slide at
its contact position (pen on the bed, no lift), :func:`pen_slide` in print orientation.

Hardware:
  1 × M5×20 ISO 4762 + 1 × M5 nut (pressed into the bar's front face) — pen thumbscrew
  1 × M2 screw through a horn hole as the pin (belongs to the servo side)

Print: default profile (``profiles/default.toml``); back face (d = slide_d0) down (the build
direction is +d in the head frame).
The sleeve bores are teardrops pointing up (+d); the V flanks are 45° and open upward.
No supports. Ream the two bores with a 6.2 mm drill if they print tight.
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, linear_extrude, polygon

from plotter_cad.geometry import FN_HOLE, handle, set_handles, teardrop
from plotter_cad.loads import PEN_DRAG, PEN_KNOCK, PEN_PRESSURE, SERVO_STALL, lever_couple
from plotter_cad.params import FRAME, PEN, TOL
from plotter_cad.part import DisplacementLimit, FemSpec, Force, LoadCase, Moment, Part, Support
from plotter_cad.regions import Box, Cylinder
from plotter_cad.types import Matrix, Vec3

if TYPE_CHECKING:
    from pythonscad import Solid


#: Thumbscrew: on the yoke bar's front face (pen side), along +d toward the pen
THUMBSCREW: Matrix = handle([PEN.pen_x, PEN.yoke_bar_d[1], sum(PEN.yoke_z) / 2], [-90, 0, 0])
#: Its nut: pressed into the yoke bar from the front, same axis
THUMBSCREW_NUT: Matrix = handle(
    [PEN.pen_x, PEN.yoke_bar_d[1] - TOL.nut_trap_h(5), sum(PEN.yoke_z) / 2], [-90, 0, 0]
)


def _box(x0: float, x1: float, d0: float, d1: float, z0: float, z1: float) -> Solid:
    """Box between the given head-frame extents."""
    return cube([x1 - x0, d1 - d0, z1 - z0]).translate([x0, d0, z0])


def _body() -> Solid:
    """Sleeve column, V-block, yoke and lug before the holes."""
    p = PEN
    z0, z1 = p.slide_z0, p.slide_z0 + p.slide_h
    r = p.sleeve_od / 2
    column = cylinder(d=p.sleeve_od, h=p.slide_h, fn=FN_HOLE).translate(
        [p.rod_x, p.rod_d_pos, z0]
    ) | _box(p.rod_x - r, p.rod_x + r, p.slide_d0, p.rod_d_pos, z0, z1)
    h = p.block_half_w
    v_profile = polygon(
        [
            [p.pen_x - h, p.slide_d0],
            [p.pen_x + h, p.slide_d0],
            [p.pen_x + h, p.apex_d + h],
            [p.pen_x, p.apex_d],
            [p.pen_x - h, p.apex_d + h],
        ]
    )
    block = linear_extrude(v_profile, height=p.slide_h).translate([0, 0, z0])
    bar_d0, bar_d1 = p.yoke_bar_d
    yz0, yz1 = p.yoke_z
    yoke = _box(p.pen_x - h, p.pen_x + h, bar_d0, bar_d1, yz0, yz1)
    for sx in (-1, 1):
        x_in, x_out = sorted((p.pen_x + sx * p.yoke_in, p.pen_x + sx * h))
        yoke = yoke | _box(x_in, x_out, p.apex_d + p.yoke_in, bar_d1, yz0, yz1)
    lug = _box(p.lug_x0, p.rod_x, p.slide_d0, p.slide_d0 + p.lug_t, *p.lug_z)
    return column | block | yoke | lug


def _cuts() -> list[Solid]:
    """Sleeve bores with the relief between them, the V-block's pen space, the slot, the
    key groove and the thumbscrew hole with its nut pocket."""
    p = PEN
    z0, z1 = p.slide_z0, p.slide_z0 + p.slide_h
    bore_d = TOL.slide_d(p.rod_d)
    relief_d = bore_d + 1.2

    def bore(d: float, za: float, zb: float) -> Solid:
        return linear_extrude(teardrop(d), height=zb - za).translate([p.rod_x, p.rod_d_pos, za])

    cuts = [
        bore(bore_d, z0 - 1, z0 + p.sleeve_len),
        bore(relief_d, z0 + p.sleeve_len - 0.01, z1 - p.sleeve_len + 0.01),
        bore(bore_d, z1 - p.sleeve_len, z1 + 1),
    ]
    slot_x0, slot_x1 = p.slot_x
    cuts.append(
        _box(
            slot_x0,
            slot_x1,
            p.slide_d0 - 1,
            p.slide_d0 + p.lug_t + 1,
            p.slot_ceiling_z - p.pin_travel - p.pin_d - p.slot_extra_h,
            p.slot_ceiling_z,
        )
    )
    cuts.append(
        _box(
            p.key_x - TOL.slide_d(p.key_w) / 2,
            p.key_x + TOL.slide_d(p.key_w) / 2,
            p.slide_d0 - 1,
            p.slide_d0 + p.key_h + TOL.gap,
            0,
            200,
        )
    )
    bar_d0, bar_d1 = p.yoke_bar_d
    zc = sum(p.yoke_z) / 2
    cuts.append(
        cylinder(d=TOL.bolt_hole_d(5), h=bar_d1 - bar_d0 + 2, fn=FN_HOLE)
        .rotate([-90, 0, 0])
        .translate([p.pen_x, bar_d0 - 1, zc])
    )
    nut_t = TOL.nut_trap_h(5)
    cuts.append(
        cylinder(d=TOL.nut_trap_ac(5), h=nut_t + 1, fn=6)
        .rotate([-90, 0, 0])
        .translate([p.pen_x, bar_d1 - nut_t, zc])
    )
    return cuts


def pen_slide_head() -> Solid:
    """The slide in the head frame, at its contact position."""
    slide = _body()
    for cut in _cuts():
        slide = slide - cut
    return set_handles(slide, thumbscrew=THUMBSCREW, thumbscrew_nut=THUMBSCREW_NUT)


def pen_slide() -> Solid:
    """The slide in print orientation: back face down, V open upward."""
    return pen_slide_head().rotate([90, 0, 0]).translate([0, 0, -PEN.slide_d0])


# --- FEM definition (head frame = installed frame; build direction +d) ----------------
_BLOCK_Z = PEN.yoke_z
_BLOCK_MID: Vec3 = (PEN.pen_x, PEN.apex_d + 6, sum(_BLOCK_Z) / 2)
#: The pen as held: a 10 mm pen, its tip on the bed
_PEN_TIP: Vec3 = (PEN.pen_x, PEN.pen_axis_d(10.0), FRAME.bed_top_z)
#: The V-block's flanks, where the pen presses
V_FLANKS = Box(
    (PEN.pen_x - PEN.block_half_w, PEN.apex_d, _BLOCK_Z[0]),
    (PEN.pen_x + PEN.block_half_w, PEN.apex_d + PEN.block_half_w, _BLOCK_Z[1]),
    facing=(0, 1, 0),
    facing_tol_deg=60,
)
#: The same volume for the displacement of the pen's seat
PEN_SEAT = Box(V_FLANKS.lo, V_FLANKS.hi)
#: The slot's ceiling, lifted by the servo horn's pin
SLOT_CEILING = Box(
    (PEN.slot_x[0], PEN.slide_d0 - 0.5, PEN.slot_ceiling_z - 0.3),
    (PEN.slot_x[1], PEN.slide_d0 + PEN.lug_t + 0.5, PEN.slot_ceiling_z + 0.3),
    facing=(0, 0, -1),
)
_BORE_R = TOL.slide_d(PEN.rod_d) / 2 + 0.6
#: The two sleeve bores on the rod (held in x and d; free to slide along z)
SLEEVES = [
    Cylinder(
        (PEN.rod_x, PEN.rod_d_pos, zc),
        (0, 0, 1),
        _BORE_R,
        PEN.sleeve_len / 2 - 0.2,
    )
    for zc in (
        PEN.slide_z0 + PEN.sleeve_len / 2,
        PEN.slide_z0 + PEN.slide_h - PEN.sleeve_len / 2,
    )
]
#: The key rib's groove walls in the lug (hold the slide against turning on the rod)
KEY_GROOVE = Box(
    (PEN.key_x - 2.5, PEN.slide_d0 - 0.2, PEN.lug_z[0]),
    (PEN.key_x + 2.5, PEN.slide_d0 + PEN.key_h + 0.5, PEN.lug_z[1]),
)
#: The sleeve column's top end, which meets the upper arm when the servo lifts it fully
TOP_STOP = Box(
    (PEN.rod_x - PEN.sleeve_od / 2, PEN.slide_d0, PEN.slide_z0 + PEN.slide_h - 0.3),
    (PEN.rod_x + PEN.sleeve_od / 2, PEN.rod_d_pos + PEN.sleeve_od / 2, PEN.slide_z0 + PEN.slide_h),
    facing=(0, 0, 1),
)


def _at_pen(name: str, description: str, force: Vec3, source: str) -> LoadCase:
    """A force at the pen tip, moved to the V-block with its couple."""
    arm = (_PEN_TIP[0] - _BLOCK_MID[0], _PEN_TIP[1] - _BLOCK_MID[1], _PEN_TIP[2] - _BLOCK_MID[2])
    return LoadCase(
        name,
        description,
        (Force(V_FLANKS, force), Moment(V_FLANKS, lever_couple(arm, force))),
        source,
    )


def _limit(axis: str, direction: Vec3) -> DisplacementLimit:
    """The pen seat's allowed movement while drawing."""
    return DisplacementLimit(f"pen_seat_{axis}", PEN_SEAT, 0.05, direction, ("pen_contact",))


PART = Part(
    name="pen_slide",
    description="Pen slide: sleeves on the rod, V-block for the pen, lug for the servo horn",
    build=pen_slide_head,
    frame="installed",
    build_direction=(0, 1, 0),
    fem=FemSpec(
        load_cases=(
            _at_pen(
                "pen_contact",
                "Pen pressure (up) and the drag it causes (sideways) at the pen tip",
                (PEN_DRAG, 0.0, PEN_PRESSURE),
                "loads.PEN_PRESSURE, loads.PEN_DRAG",
            ),
            _at_pen(
                "pen_knock_x",
                f"A hand or a curled sheet knocks the pen tip sideways with {PEN_KNOCK:g} N",
                (PEN_KNOCK, 0.0, 0.0),
                "loads.PEN_KNOCK",
            ),
            _at_pen(
                "pen_knock_d",
                f"The pen is knocked back toward the carriage with {PEN_KNOCK:g} N",
                (0.0, -PEN_KNOCK, 0.0),
                "loads.PEN_KNOCK",
            ),
            LoadCase(
                "servo_stall",
                "The servo, stalled against the upper stop, pushes the slot's ceiling up",
                (Force(SLOT_CEILING, (0.0, 0.0, SERVO_STALL)),),
                "loads.SERVO_STALL",
            ),
        ),
        supports=(
            Support(
                "sleeve_low",
                SLEEVES[0],
                "Lower sleeve on the rod: held in x and d, free along the rod",
                constrain=(True, True, False),
            ),
            Support(
                "sleeve_high",
                SLEEVES[1],
                "Upper sleeve on the rod: held in x and d, free along the rod",
                constrain=(True, True, False),
            ),
            Support(
                "key_groove",
                KEY_GROOVE,
                "Key rib's groove: holds the slide against turning (x)",
                constrain=(True, False, False),
            ),
            Support(
                "top_stop",
                TOP_STOP,
                "Top end against the upper arm: holds z (matters for the servo stall; the "
                "pen's lift is balanced by the weight)",
                constrain=(False, False, True),
            ),
        ),
        displacement_limits=(
            _limit("x", (1, 0, 0)),
            _limit("d", (0, 1, 0)),
            _limit("z", (0, 0, 1)),
        ),
    ),
)
