"""Pen holder body: the fixed half of the v1 tool head (STATUS.md T3.6). Print ×1.

Purpose: hangs on the carriage's tool-plate interface (hook lip + 2 × M3), holds the Ø6 rod
that the pen slide rides on, and carries the FT90M servo in a wall with a window (the servo
lies with its output facing the plate, so the horn swings in the gap behind the wall). A
key rib on the plate face keeps the slide from turning on the rod.

  side section (looking along +x; carriage on the left, d = distance in front of it)

   lip ┐  plate  upper arm ───── rod ──────┐
       ▒▒▒▒▒▒▒▒▒                            │ ╲ rod passes the slide's two sleeves
       ▒ key rib   ░ slide ░                │
       ▒▒▒▒▒▒▒▒▒   lower arm ──── rod seat──┘     servo wall ┃ servo →

Frame: the head frame of ``params.PenHolder`` (x across, d forward from the carriage face,
z absolute); :func:`pen_holder_body_head` returns the part there, :func:`pen_holder_body`
in print orientation.

Hardware:
  1 × Ø6 rod, ``PEN.rod_len`` long, pressed into the arms (a drop of glue if loose)
  2 × M3×10 ISO 4762 — through the plate into the carriage's captive nuts
  2 × the servo's own screws (self-tapping, into the Ø1.6 pilot holes in the wall)

Print: default profile (``profiles/default.toml``); on its left side (x = −25 face
down; the build direction is +x in the head frame). The hook lip, ribs and webs are then
plain extrusions; the holes along d and z are teardrops pointing up (+x). No supports.

FEM: pen knocks reach the arms through the rod, the servo's stall pushes the upper arm and
twists the servo wall; the plate's back face is held; see :data:`PART`.
"""

from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE, teardrop
from cadder.handles import handle, set_handles
from cadder.hardware import FT90M
from cadder.regions import Box, Cylinder
from cadder.types import Matrix, Vec3
from pythonscad import cube, cylinder, linear_extrude, polygon

from plotzker.loads import PEN_KNOCK, SERVO_STALL
from plotzker.params import FRAME, PEN, TOL, TOOL_PLATE
from plotzker.part import FemSpec, Force, LoadCase, Moment, Part, Support

if TYPE_CHECKING:
    from pythonscad import Solid

PILOT_D = 1.6  #: pilot hole for the servo's self-tapping screws. ASSUMED

#: Rod: bottom end (seated in the lower arm), axis along +z
ROD: Matrix = handle([PEN.rod_x, PEN.rod_d_pos, PEN.upper_arm_top - PEN.rod_len])
#: Servo: output facing the plate, in the window (its own model is turned into place)
SERVO: Matrix = handle([PEN.servo_x, PEN.servo_front_d, PEN.servo_center_z], [0, 90, 270])
#: Horn: on the servo shaft, in the gap behind the wall; the model is turned about its own
#: axis by the pen-lift angle before it is aligned
HORN: Matrix = handle([PEN.servo_x, PEN.horn_d[0], PEN.shaft_z], [-90, 0, 0])
#: Clamp screws (tool plate to carriage): at the counterbore floors, along +d into the carriage
CLAMP_SCREWS = [
    handle(
        [
            sx * TOOL_PLATE.screw_pitch / 2,
            PEN.plate_d[1] - 3,
            TOOL_PLATE.bottom_z + TOOL_PLATE.screw_z,
        ],
        [-90, 0, 0],
    )
    for sx in (-1, 1)
]


def _box(x0: float, x1: float, d0: float, d1: float, z0: float, z1: float) -> Solid:
    """Box between the given head-frame extents."""
    return cube([x1 - x0, d1 - d0, z1 - z0]).translate([x0, d0, z0])


def _hole_d(d: float, x: float, z: float, d0: float, d1: float) -> Solid:
    """Hole along d from ``d0`` to ``d1``: a teardrop pointing +x (up in the print)."""
    return (
        linear_extrude(teardrop(d).rotate([0, 0, -90]), height=d1 - d0, center=True)
        .rotate([90, 0, 0])
        .translate([x, (d0 + d1) / 2, z])
    )


def _hole_z(d: float, x: float, d_pos: float, z0: float, z1: float) -> Solid:
    """Hole along z from ``z0`` to ``z1``: a teardrop pointing +x (up in the print)."""
    return linear_extrude(teardrop(d).rotate([0, 0, -90]), height=z1 - z0).translate([x, d_pos, z0])


def _plate_and_lip() -> Solid:
    """Plate, the spine above it and the hook lip that drops into the carriage groove."""
    tp, g = TOOL_PLATE, TOOL_PLATE.fit_gap
    d0, d1 = PEN.plate_d
    top = tp.top_z
    plate = _box(-tp.w / 2, tp.w / 2, d0, d1, tp.bottom_z, top - g)
    spine = _box(-tp.w / 2, PEN.rod_x + PEN.arm_w / 2, d0, d1, top - g - 1, PEN.upper_arm_top)
    # lip: the carriage groove (opening hook_h, 45° undercut hook_d) shrunk by the gap;
    # profile in (d, z), negative d = into the carriage
    profile = polygon(
        [
            [d0 + 1, top - g],
            [-(tp.hook_d - g), top - g],
            [-(tp.hook_d - g), top - tp.hook_h - tp.hook_d + 2 * g],
            [0, top - tp.hook_h + g],
            [d0 + 1, top - tp.hook_h + g],
        ]
    )
    lip = linear_extrude(profile, height=tp.w, center=True).rotate([90, 0, 90])
    return plate | spine | lip


def _screw_holes() -> list[Solid]:
    """M3 clearance holes with counterbores for the clamp screws."""
    tp = TOOL_PLATE
    d0, d1 = PEN.plate_d
    z = tp.bottom_z + tp.screw_z
    cuts = []
    for sx in (-1, 1):
        x = sx * tp.screw_pitch / 2
        cuts.append(_hole_d(TOL.bolt_hole_d(3), x, z, d0 - 1, d1 + 1))
        cuts.append(_hole_d(TOL.cbore_d(3), x, z, d1 - 3, d1 + 1))
    return cuts


def _rod_arms() -> tuple[list[Solid], list[Solid]]:
    """Both rod arms and the rod holes (parts to add, cuts to subtract)."""
    p = PEN
    x0, x1 = p.rod_x - p.arm_w / 2, p.rod_x + p.arm_w / 2
    d0 = p.plate_d[1] - 1

    def arm(z0: float, z1: float) -> Solid:
        """Round boss around the rod, joined to the plate."""
        boss = cylinder(d=p.arm_w, h=z1 - z0, fn=FN_HOLE).translate([p.rod_x, p.rod_d_pos, z0])
        return boss | _box(x0, x1, d0, p.rod_d_pos, z0, z1)

    hole_d = TOL.press_d(p.rod_d)
    cuts = [
        _hole_z(
            hole_d, p.rod_x, p.rod_d_pos, p.lower_arm_top - p.rod_seat_depth, p.lower_arm_top + 1
        ),
        _hole_z(hole_d, p.rod_x, p.rod_d_pos, p.upper_arm_bottom - 1, p.upper_arm_top + 1),
    ]
    return [
        arm(p.lower_arm_bottom, p.lower_arm_top),
        arm(p.upper_arm_bottom, p.upper_arm_top),
    ], cuts


def _servo_bracket() -> tuple[list[Solid], list[Solid]]:
    """Servo wall, outer rib and webs, with the window and pilot holes."""
    p = PEN
    x0, x1 = p.wall_x
    z0, z1 = p.wall_z
    d_front = p.wall_d
    d_back = d_front - p.wall_t
    plate_front = p.plate_d[1] - 1
    web_x1 = p.lug_x0 - TOL.gap * 2  # the lug rides past the webs
    wall = _box(x0, x1, d_back, d_front, z0, z1)
    rib = _box(x0, x0 + p.rib_t, plate_front, d_front, z0, z1)
    webs = [
        _box(x0, web_x1, plate_front, d_front, z0, z0 + p.web_t),
        _box(x0, web_x1, plate_front, d_front, z1 - p.web_t, z1),
    ]
    length, width, _ = FT90M.body
    zc, c = p.servo_center_z, p.servo_clear
    window = _box(
        p.servo_x - width / 2 - c,
        p.servo_x + width / 2 + c,
        d_back - 1,
        d_front + 1,
        zc - length / 2 - c,
        zc + length / 2 + c,
    )
    pilots = [
        _hole_d(PILOT_D, p.servo_x, zc + sz * FT90M.hole_pitch / 2, d_back - 1, d_front + 1)
        for sz in (-1, 1)
    ]
    return [wall, rib, *webs], [window, *pilots]


def _key_rib() -> Solid:
    """Rib on the plate face that the slide's lug rides on."""
    p = PEN
    z0 = p.lug_z[0] - p.sink
    z1 = p.lug_z[1] + p.lift
    return _box(
        p.key_x - p.key_w / 2,
        p.key_x + p.key_w / 2,
        p.plate_d[1] - 1,
        p.plate_d[1] + p.key_h,
        z0,
        z1,
    )


def pen_holder_body_head() -> Solid:
    """The body in the head frame (x across, d forward, z absolute)."""
    arms, arm_cuts = _rod_arms()
    bracket, bracket_cuts = _servo_bracket()
    body = _plate_and_lip()
    for part in [*arms, *bracket, _key_rib()]:
        body = body | part
    cuts = [*_screw_holes(), *arm_cuts, *bracket_cuts]
    for cut in cuts:
        body = body - cut
    return set_handles(body, rod=ROD, servo=SERVO, horn=HORN, clamp_screws=CLAMP_SCREWS)


def pen_holder_body() -> Solid:
    """The body in print orientation: on its left side (x = −25), lip toward the bed edge."""
    body = pen_holder_body_head().rotate([0, -90, 0])
    return body.translate([0, 0, TOOL_PLATE.w / 2])


# --- FEM definition (head frame = installed frame; build direction +x) -----------------
_ROD_BORE_R = TOL.press_d(PEN.rod_d) / 2 + 0.3
_UPPER_Z = (PEN.upper_arm_bottom, PEN.upper_arm_top)
#: The upper arm's rod hole (the rod bears on its wall) and the lower arm's blind rod seat
UPPER_BORE = Cylinder(
    (PEN.rod_x, PEN.rod_d_pos, sum(_UPPER_Z) / 2),
    (0, 0, 1),
    _ROD_BORE_R,
    (_UPPER_Z[1] - _UPPER_Z[0]) / 2,
)
LOWER_SEAT = Cylinder(
    (PEN.rod_x, PEN.rod_d_pos, PEN.lower_arm_top - PEN.rod_seat_depth / 2),
    (0, 0, 1),
    _ROD_BORE_R,
    PEN.rod_seat_depth / 2,
)
#: The upper arm's underside, which the slide meets at the top of its travel
UPPER_STOP = Box(
    (PEN.rod_x - PEN.arm_w / 2, PEN.rod_d_pos - PEN.arm_w / 2, PEN.upper_arm_bottom - 0.3),
    (PEN.rod_x + PEN.arm_w / 2, PEN.rod_d_pos + PEN.arm_w / 2, PEN.upper_arm_bottom + 0.3),
    facing=(0, 0, -1),
)
_SERVO_ZC = PEN.servo_center_z
#: Where the servo's tabs bear on the wall (its screws pull them on), either side of the window
SERVO_SEAT = Box(
    (PEN.servo_x - FT90M.body[1] / 2 - 2, PEN.wall_d - 0.3, _SERVO_ZC - FT90M.hole_pitch / 2 - 4),
    (PEN.servo_x + FT90M.body[1] / 2 + 2, PEN.wall_d + 0.3, _SERVO_ZC + FT90M.hole_pitch / 2 + 4),
    facing=(0, 1, 0),
)
#: The plate's back face against the carriage (held there by the hook lip and the clamp screws)
PLATE_BACK = Box(
    (-TOOL_PLATE.w / 2, PEN.plate_d[0] - 0.3, TOOL_PLATE.bottom_z),
    (TOOL_PLATE.w / 2, PEN.plate_d[0] + 0.3, TOOL_PLATE.top_z),
    facing=(0, -1, 0),
)
_TIP_Z = FRAME.bed_top_z
_Z_LOW = PEN.lower_arm_top - PEN.rod_seat_depth / 2
_Z_HIGH = sum(_UPPER_Z) / 2
#: A force at the pen tip, below the lower arm, loads the two arms through the rod: the lower
#: one with (1 + a) times the force and the upper one against it with a times, a = overhang ratio
_OVERHANG = (_Z_LOW - _TIP_Z) / (_Z_HIGH - _Z_LOW)


def _knock(name: str, direction: Vec3) -> LoadCase:
    """A pen knock as the rod's reactions on the two arms."""
    f = PEN_KNOCK
    lower = tuple(c * f * (1 + _OVERHANG) for c in direction)
    upper = tuple(-c * f * _OVERHANG for c in direction)
    return LoadCase(
        name,
        f"The pen tip is knocked with {f:g} N; the rod passes it to the arms "
        f"({1 + _OVERHANG:.1f} × on the lower seat, {_OVERHANG:.1f} × opposite on the upper hole)",
        (
            Force(LOWER_SEAT, (lower[0], lower[1], lower[2]), bearing=True),
            Force(UPPER_BORE, (upper[0], upper[1], upper[2]), bearing=True),
        ),
        "loads.PEN_KNOCK",
    )


_STALL = LoadCase(
    "servo_stall",
    "The servo stalls with the slide against the upper stop: the stop pushes up on the arm; the "
    "servo's reaction pulls the wall down and twists it",
    (
        Force(UPPER_STOP, (0.0, 0.0, SERVO_STALL)),
        Force(SERVO_SEAT, (0.0, 0.0, -SERVO_STALL)),
        Moment(SERVO_SEAT, (0.0, SERVO_STALL * 17.0, 0.0)),
    ),
    "loads.SERVO_STALL",
)

PART = Part(
    name="pen_holder_body",
    description="Pen holder body: plate on the carriage, rod arms and the servo wall",
    build=pen_holder_body_head,
    frame="installed",
    build_direction=(1, 0, 0),
    fem=FemSpec(
        load_cases=(_knock("pen_knock_x", (1, 0, 0)), _knock("pen_knock_d", (0, 1, 0)), _STALL),
        supports=(
            Support(
                "plate_back",
                PLATE_BACK,
                "Plate pressed on the carriage face (hook lip and 2 x M3): held fully",
            ),
        ),
        default_displacement_limit_mm=None,
    ),
)
