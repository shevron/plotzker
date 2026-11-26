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

Print: default profile (``profiles/default.toml``); back face (d = slide_depth_start) down (the build
direction is +d in the head frame).
The sleeve bores are teardrops pointing up (+d); the V flanks are 45° and open upward.
No supports. Ream the two bores with a 6.2 mm drill if they print tight.
"""

from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE, lever_couple, teardrop
from cadder.handles import handle, set_handles
from cadder.part import DisplacementLimit, FemSpec, Force, LoadCase, Moment, PrintedPart, Support
from cadder.regions import Box, Cylinder
from cadder.types import Matrix, Vec3
from pythonscad import cube, cylinder, linear_extrude, polygon

from plotzker.loads import PEN_DRAG, PEN_KNOCK, PEN_PRESSURE, SERVO_STALL
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import FRAME, PEN, TOL

if TYPE_CHECKING:
    from pythonscad import Solid


#: Thumbscrew: on the yoke bar's front face (pen side), along +d toward the pen
THUMBSCREW: Matrix = handle([PEN.pen_x, PEN.yoke_bar_depth[1], sum(PEN.yoke_z) / 2], [-90, 0, 0])
#: Its nut: pressed into the yoke bar from the front, same axis
THUMBSCREW_NUT: Matrix = handle(
    [PEN.pen_x, PEN.yoke_bar_depth[1] - TOL.nut_trap_height(5), sum(PEN.yoke_z) / 2], [-90, 0, 0]
)


def _box(x0: float, x1: float, d0: float, d1: float, z0: float, z1: float) -> Solid:
    """Box between the given head-frame extents."""
    return cube([x1 - x0, d1 - d0, z1 - z0]).translate([x0, d0, z0])


def _body() -> Solid:
    """Sleeve column, V-block, yoke and lug before the holes."""
    z0, z1 = PEN.slide_z0, PEN.slide_z0 + PEN.slide_h
    r = PEN.sleeve_outer_dia / 2
    column = cylinder(d=PEN.sleeve_outer_dia, h=PEN.slide_h, fn=FN_HOLE).translate(
        [PEN.rod_x, PEN.rod_depth, z0]
    ) | _box(PEN.rod_x - r, PEN.rod_x + r, PEN.slide_depth_start, PEN.rod_depth, z0, z1)
    h = PEN.block_half_width
    v_profile = polygon(
        [
            [PEN.pen_x - h, PEN.slide_depth_start],
            [PEN.pen_x + h, PEN.slide_depth_start],
            [PEN.pen_x + h, PEN.apex_depth + h],
            [PEN.pen_x, PEN.apex_depth],
            [PEN.pen_x - h, PEN.apex_depth + h],
        ]
    )
    block = linear_extrude(v_profile, height=PEN.slide_h).translate([0, 0, z0])
    bar_d0, bar_d1 = PEN.yoke_bar_depth
    yz0, yz1 = PEN.yoke_z
    yoke = _box(PEN.pen_x - h, PEN.pen_x + h, bar_d0, bar_d1, yz0, yz1)
    for sx in (-1, 1):
        x_in, x_out = sorted((PEN.pen_x + sx * PEN.yoke_in, PEN.pen_x + sx * h))
        yoke = yoke | _box(x_in, x_out, PEN.apex_depth + PEN.yoke_in, bar_d1, yz0, yz1)
    lug = _box(PEN.lug_x0, PEN.rod_x, PEN.slide_depth_start, PEN.slide_depth_start + PEN.lug_thickness, *PEN.lug_z)
    return column | block | yoke | lug


def _cuts() -> list[Solid]:
    """Sleeve bores with the relief between them, the V-block's pen space, the slot, the
    key groove and the thumbscrew hole with its nut pocket."""
    z0, z1 = PEN.slide_z0, PEN.slide_z0 + PEN.slide_h
    bore_dia = TOL.slide_dia(PEN.rod_dia)
    relief_dia = bore_dia + 1.2

    def bore(d: float, za: float, zb: float) -> Solid:
        return linear_extrude(teardrop(d), height=zb - za).translate([PEN.rod_x, PEN.rod_depth, za])

    cuts = [
        bore(bore_dia, z0 - 1, z0 + PEN.sleeve_length),
        bore(relief_dia, z0 + PEN.sleeve_length - 0.01, z1 - PEN.sleeve_length + 0.01),
        bore(bore_dia, z1 - PEN.sleeve_length, z1 + 1),
    ]
    slot_x0, slot_x1 = PEN.slot_x
    cuts.append(
        _box(
            slot_x0,
            slot_x1,
            PEN.slide_depth_start - 1,
            PEN.slide_depth_start + PEN.lug_thickness + 1,
            PEN.slot_ceiling_z - PEN.pin_travel - PEN.pin_dia - PEN.slot_extra_height,
            PEN.slot_ceiling_z,
        )
    )
    cuts.append(
        _box(
            PEN.key_x - TOL.slide_dia(PEN.key_width) / 2,
            PEN.key_x + TOL.slide_dia(PEN.key_width) / 2,
            PEN.slide_depth_start - 1,
            PEN.slide_depth_start + PEN.key_height + TOL.gap,
            0,
            200,
        )
    )
    bar_d0, bar_d1 = PEN.yoke_bar_depth
    zc = sum(PEN.yoke_z) / 2
    cuts.append(
        cylinder(d=TOL.bolt_hole_dia(5), h=bar_d1 - bar_d0 + 2, fn=FN_HOLE)
        .rotate([-90, 0, 0])
        .translate([PEN.pen_x, bar_d0 - 1, zc])
    )
    nut_thickness = TOL.nut_trap_height(5)
    cuts.append(
        cylinder(d=TOL.nut_trap_across_corners(5), h=nut_thickness + 1, fn=6)
        .rotate([-90, 0, 0])
        .translate([PEN.pen_x, bar_d1 - nut_thickness, zc])
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
    return pen_slide_head().rotate([90, 0, 0]).translate([0, 0, -PEN.slide_depth_start])


# --- FEM definition (head frame = installed frame; build direction +d) ----------------
_BLOCK_Z = PEN.yoke_z
_BLOCK_MID: Vec3 = (PEN.pen_x, PEN.apex_depth + 6, sum(_BLOCK_Z) / 2)
#: The pen as held: a 10 mm pen, its tip on the bed
_PEN_TIP: Vec3 = (PEN.pen_x, PEN.pen_axis_depth(10.0), FRAME.bed_top_z)
#: The V-block's flanks, where the pen presses
V_FLANKS = Box(
    (PEN.pen_x - PEN.block_half_width, PEN.apex_depth, _BLOCK_Z[0]),
    (PEN.pen_x + PEN.block_half_width, PEN.apex_depth + PEN.block_half_width, _BLOCK_Z[1]),
    facing=(0, 1, 0),
    facing_tol_deg=60,
)
#: The same volume for the displacement of the pen's seat
PEN_SEAT = Box(V_FLANKS.lo, V_FLANKS.hi)
#: The slot's ceiling, lifted by the servo horn's pin
SLOT_CEILING = Box(
    (PEN.slot_x[0], PEN.slide_depth_start - 0.5, PEN.slot_ceiling_z - 0.3),
    (PEN.slot_x[1], PEN.slide_depth_start + PEN.lug_thickness + 0.5, PEN.slot_ceiling_z + 0.3),
    facing=(0, 0, -1),
)
_BORE_R = TOL.slide_dia(PEN.rod_dia) / 2 + 0.6
#: The two sleeve bores on the rod (held in x and d; free to slide along z)
SLEEVES = [
    Cylinder(
        (PEN.rod_x, PEN.rod_depth, zc),
        (0, 0, 1),
        _BORE_R,
        PEN.sleeve_length / 2 - 0.2,
    )
    for zc in (
        PEN.slide_z0 + PEN.sleeve_length / 2,
        PEN.slide_z0 + PEN.slide_h - PEN.sleeve_length / 2,
    )
]
#: The key rib's groove walls in the lug (hold the slide against turning on the rod)
KEY_GROOVE = Box(
    (PEN.key_x - 2.5, PEN.slide_depth_start - 0.2, PEN.lug_z[0]),
    (PEN.key_x + 2.5, PEN.slide_depth_start + PEN.key_height + 0.5, PEN.lug_z[1]),
)
#: The sleeve column's top end, which meets the upper arm when the servo lifts it fully
TOP_STOP = Box(
    (PEN.rod_x - PEN.sleeve_outer_dia / 2, PEN.slide_depth_start, PEN.slide_z0 + PEN.slide_h - 0.3),
    (PEN.rod_x + PEN.sleeve_outer_dia / 2, PEN.rod_depth + PEN.sleeve_outer_dia / 2, PEN.slide_z0 + PEN.slide_h),
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


PART = PrintedPart(
    name="pen_slide",
    description="Pen slide: sleeves on the rod, V-block for the pen, lug for the servo horn",
    build=pen_slide,
    analysis=pen_slide_head,
    frame="installed",
    build_direction=(0, 1, 0),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
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
