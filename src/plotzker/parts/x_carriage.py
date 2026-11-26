"""X carriage on the upright 4020 beam (STATUS.md T3.3). Print ×1.

Purpose: carries the tool head. Four V-wheels ride the beam's top and bottom grooves
(bottom pair on eccentric spacers for preload, D21). A bridge under the middle of the
beam reaches a rear block that clamps both ends of the X belt's lower run (vertical loop
behind the beam) and carries the X endstop trigger. The front face has the tool-plate
interface (hook groove + 2 × M3); a top tab holds the tool-head connector and a
zip-tie strain relief.

  side section (looking along +x)            front view
             ┌tab┐ connector                     ┌─tab─┐
     bridge  │   ├──────────┐ rear block        ┌┴──────┴┐
  ┌──────────┤   │  ◯ wheel │ ▄ X belt clamp    │◯      ◯│ top wheels
  │ plate    │   │ ┌──beam──┐                   │ ═hook═ │
  │ (front   │   │ │  4020  │                   │ ⊕    ⊕ │ ← 2 × M3 (tool plate)
  │  face =  │   │ └────────┘                   │◎      ◎│ bottom wheels (eccentric)
  │  tool    │   │  ◯ wheel                     └────────┘
  │  plate)  │                                     ↑ tool plate 50 wide fits between

Frame (carriage-local, see ``params.Carriage``): x from the carriage center along the
beam, y from the beam's center plane (+y behind the beam), z = machine z. The part is
modeled installed (:func:`x_carriage_installed`), then rotated so the FRONT FACE lies
on the print bed (:func:`x_carriage`).

Hardware:
  4 × V-wheel Ø24 × 10 (625 bearings)
  2 × eccentric spacer (bottom wheels, D21)
  4 × M5×42 ISO 4762 + 4 × M5 washers (front, in 2 mm counterbores) + 4 × M5 nuts (nyloc preferred)
  2 × M3 nuts (pressed in from the bottom edge) — tool-plate clamp screws (tool head
      supplies the M3 screws)
  4 × M3 nuts (rear pair pressed in from the back face, front pair from the block's ends)
      + 4 × M3×14 ISO 4762 + 2 × belt_clamp (printed) — X belt
  1 × M3×12 ISO 4762 + 2 × M3 nuts — X endstop trigger: screwed into the rear block's
      left end through a captive nut; its head touches the switch; lock nut outside
  zip ties for the tool-head cable

Print: default profile (``profiles/default.toml``); front face down on the bed (the build
direction is +y in the carriage frame); no supports (hook groove and side holes are
self-supporting: 45° walls, short bridges, teardrops).

FEM: the X belt's two ends pull the rear block apart, the tool head's weight and inertia and a
pen knock act on the tool-plate face, and the wheel axle bolts' head seats hold it; see
:data:`PART`.
"""

from typing import TYPE_CHECKING

from cadder.geometry import EPS, FN_HOLE, lever_couple, teardrop_x
from cadder.handles import handle, set_handles
from cadder.hardware import ECCENTRIC, metric
from cadder.part import (
    DisplacementLimit,
    FemSpec,
    Force,
    Load,
    LoadCase,
    Moment,
    PrintedPart,
    Support,
)
from cadder.printing import nut_slot
from cadder.regions import Box, Cylinder
from cadder.types import Matrix, Vec3
from pythonscad import cube, cylinder, hull, linear_extrude, polygon

from plotzker.loads import ACCELERATION, CARRIAGE_HEAD_KG, PEN_KNOCK, PEN_TIP_Z, X_BELT_LOADS, G
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import BEAM, CARRIAGE, CLAMP, TOL, TOOL_PLATE, X_BELT

if TYPE_CHECKING:
    from pythonscad import Solid

WHEEL_X = CARRIAGE.wheel_pitch_x / 2  #: wheel axle x (±)
REAR_Y0 = BEAM.depth / 2 + 0.5  #: the bridge ends and widens here (behind the beam)
REAR_Y1 = X_BELT.y + CLAMP.w / 2 + 1  #: rear block back face
REAR_Y_FULL = REAR_Y0 + (CARRIAGE.rear_w - CARRIAGE.bridge_w) / 2  #: the 45° flanks end here
CLAMP_X = CARRIAGE.rear_w / 2 - CLAMP.length / 2  #: X belt clamp centers (±)

#: Wheel axle bolts (top pair, bottom pair): on the plate's front face, along +y into the plate
WHEEL_AXLES_TOP = [handle([sx * WHEEL_X, CARRIAGE.plate_front_y, CARRIAGE.wheel_z[0]], [90, 0, 0]) for sx in (-1, 1)]
WHEEL_AXLES_BOTTOM = [
    handle([sx * WHEEL_X, CARRIAGE.plate_front_y, CARRIAGE.wheel_z[1]], [90, 0, 0]) for sx in (-1, 1)
]
#: X belt clamps (left, right): upside down on the rear block's flat top, belt center, along x
BELT_CLAMPS = [handle([sx * CLAMP_X - CLAMP.length / 2, X_BELT.y, X_BELT.back_z], [180, 0, 90]) for sx in (-1, 1)]
#: X endstop trigger screw: on the rear block's left end, along +x into the block
TRIGGER_SCREW: Matrix = handle([-CARRIAGE.rear_w / 2, CARRIAGE.trig_y, CARRIAGE.trig_z], [0, -90, 0])


def _body() -> Solid:
    """Carriage solid before the holes and cutouts."""
    plate = cube([CARRIAGE.plate_w, CARRIAGE.plate_t, CARRIAGE.top_z - CARRIAGE.bottom_z]).translate(
        [-CARRIAGE.plate_w / 2, CARRIAGE.plate_front_y, CARRIAGE.bottom_z]
    )
    tab = cube([CARRIAGE.tab_w, CARRIAGE.plate_t, CARRIAGE.tab_h + EPS]).translate(
        [-CARRIAGE.tab_w / 2, CARRIAGE.plate_front_y, CARRIAGE.top_z - EPS]
    )
    standoffs = [
        cylinder(d=CARRIAGE.top_boss_d, h=ECCENTRIC.stack + EPS, fn=32)
        .rotate([-90, 0, 0])
        .translate([sx * WHEEL_X, CARRIAGE.plate_back_y - EPS, CARRIAGE.wheel_z[0]])
        for sx in (-1, 1)
    ]
    bridge = cube([CARRIAGE.bridge_w, REAR_Y0 - CARRIAGE.plate_back_y + EPS, CARRIAGE.bridge_h]).translate(
        [-CARRIAGE.bridge_w / 2, CARRIAGE.plate_back_y - EPS, CARRIAGE.bridge_z]
    )
    # widening (45° in plan, at most 45° in the top flank) from the bridge into the rear block,
    # behind the beam: the top rises to the belt's bearing face
    widening = hull(
        cube([CARRIAGE.bridge_w, EPS, CARRIAGE.bridge_h]).translate(
            [-CARRIAGE.bridge_w / 2, REAR_Y0, CARRIAGE.bridge_z]
        ),
        cube([CARRIAGE.rear_w, EPS, CARRIAGE.rear_h]).translate([-CARRIAGE.rear_w / 2, REAR_Y_FULL, CARRIAGE.block_z]),
    )
    rear = cube([CARRIAGE.rear_w, REAR_Y1 - REAR_Y_FULL, CARRIAGE.rear_h]).translate(
        [-CARRIAGE.rear_w / 2, REAR_Y_FULL, CARRIAGE.block_z]
    )
    return plate | tab | standoffs | bridge | widening | rear


def _wheel_axle_holes() -> list[Solid]:
    """Wheel axle holes."""
    holes = []
    for sx in (-1, 1):
        # top wheels: M5 clearance through plate and stand-off
        holes.append(
            cylinder(d=TOL.bolt_hole_d(5), h=CARRIAGE.plate_t + ECCENTRIC.stack + 2, fn=FN_HOLE)
            .rotate([-90, 0, 0])
            .translate([sx * WHEEL_X, CARRIAGE.plate_front_y - 1, CARRIAGE.wheel_z[0]])
        )
        # bottom wheels: hole for the eccentric boss (the M5 moves ±offset inside it)
        holes.append(
            cylinder(d=TOL.slide_d(ECCENTRIC.boss_d), h=CARRIAGE.plate_t + 2, fn=FN_HOLE)
            .rotate([-90, 0, 0])
            .translate([sx * WHEEL_X, CARRIAGE.plate_front_y - 1, CARRIAGE.wheel_z[1]])
        )
        # counterbore for the bolt head and washer on the front face
        holes.append(
            cylinder(d=TOL.slide_d(metric(5).washer_od), h=CARRIAGE.head_recess + 1, fn=FN_HOLE)
            .rotate([-90, 0, 0])
            .translate([sx * WHEEL_X, CARRIAGE.plate_front_y - 1, CARRIAGE.wheel_z[0]])
        )
        holes.append(
            cylinder(d=TOL.slide_d(metric(5).washer_od), h=CARRIAGE.head_recess + 1, fn=FN_HOLE)
            .rotate([-90, 0, 0])
            .translate([sx * WHEEL_X, CARRIAGE.plate_front_y - 1, CARRIAGE.wheel_z[1]])
        )
    return holes


def _tool_plate_interface() -> list[Solid]:
    """Tool-plate hook groove and mounting holes."""
    # hook groove (French cleat): opening hook_h tall at the face, undercut hook_d
    # downward at 45°; closed ends locate the tool plate in X
    profile = polygon(
        [
            [-1, TOOL_PLATE.top_z],
            [TOOL_PLATE.hook_d, TOOL_PLATE.top_z],
            [TOOL_PLATE.hook_d, TOOL_PLATE.top_z - TOOL_PLATE.hook_h - TOOL_PLATE.hook_d],
            [0, TOOL_PLATE.top_z - TOOL_PLATE.hook_h],
            [-1, TOOL_PLATE.top_z - TOOL_PLATE.hook_h],
        ]
    )
    groove = (
        linear_extrude(profile, height=TOOL_PLATE.w + 2 * TOOL_PLATE.fit_gap, center=True)
        .rotate([90, 0, 90])
        .translate([0, CARRIAGE.plate_front_y, 0])
    )
    # M3 clearance holes through the plate; each nut is pressed into a slot from the bottom
    # edge, behind a wall on the front side that takes the pull of the tool plate's screws
    nut_t = TOL.nut_trap_h(3)
    screw_zc = TOOL_PLATE.bottom_z + TOOL_PLATE.screw_z
    nuts = []
    for sx in (-1, 1):
        x = sx * TOOL_PLATE.screw_pitch / 2
        nuts.append(
            cylinder(d=TOL.bolt_hole_d(3), h=CARRIAGE.plate_t + 2, fn=FN_HOLE)
            .rotate([-90, 0, 0])
            .translate([x, CARRIAGE.plate_front_y - 1, screw_zc])
        )
        nuts.append(
            nut_slot(3, screw_zc - TOOL_PLATE.bottom_z + 1, "y", "-z", tol=TOL).translate(
                [x, CARRIAGE.plate_front_y + TOL.nut_wall + nut_t / 2, screw_zc]
            )
        )
    return [groove, *nuts]


def _top_tab_cutouts() -> list[Solid]:
    """Windows for the top connector tabs."""
    conn_w, conn_h = TOOL_PLATE.conn_size
    window = cube([conn_w, CARRIAGE.plate_t + 2, conn_h]).translate(
        [-conn_w / 2, CARRIAGE.plate_front_y - 1, CARRIAGE.top_z + CARRIAGE.tab_h - 3 - conn_h]
    )
    slot_w, slot_h = CARRIAGE.zip_slot
    zip_slots = [
        cube([slot_w, CARRIAGE.plate_t + 2, slot_h]).translate(
            [
                sx * (conn_w / 2 + 1 + slot_w / 2) - slot_w / 2,
                CARRIAGE.plate_front_y - 1,
                CARRIAGE.top_z - 2 - slot_h,
            ]
        )  # above the bridge
        for sx in (-1, 1)
    ]
    return [window, *zip_slots]


def _belt_clamp_cutouts() -> list[Solid]:
    """Belt clamp screw holes and nut slots (the rear block's top is flat)."""
    nut_z = X_BELT.back_z - CLAMP.nut_z - TOL.nut_trap_h(3) / 2  #: nut center (roof above it)
    cuts = []
    for sx in (-1, 1):
        x = sx * CLAMP_X
        for sy in (-1, 1):
            y = X_BELT.y + sy * CLAMP.screw_dx
            cuts.append(
                cylinder(d=TOL.bolt_hole_d(3), h=CLAMP.nut_z + 1, fn=FN_HOLE).translate(
                    [x, y, X_BELT.back_z + EPS - CLAMP.nut_z - 1]
                )
            )
            # each nut has its own pocket: the rear one is pressed in from the back face, the
            # front one from the block's end (the nearer one), flat-first (T3.13)
            if sy > 0:
                slot = nut_slot(3, REAR_Y1 + 1 - y, "z", "+y", tol=TOL)
            else:
                slot = nut_slot(3, CARRIAGE.rear_w / 2 + 1 - CLAMP_X, "z", "+x" if sx > 0 else "-x", tol=TOL)
            cuts.append(slot.translate([x, y, nut_z]))
    return cuts


def _endstop_trigger_cutouts() -> list[Solid]:
    """M3 along -x from the rear block's left end, through a captive nut."""
    screw = (
        teardrop_x(TOL.slide_d(3), 18)  # snug: the screw must not wobble (T3.14)
        .rotate([-90, 0, 0])
        .translate([-CARRIAGE.rear_w / 2 + 8, CARRIAGE.trig_y, CARRIAGE.trig_z])
    )
    # the nut is pressed in from the underside (the belt bears on the top face)
    nut = nut_slot(3, CARRIAGE.trig_z - CARRIAGE.block_z + 1, "x", "-z", tol=TOL).translate(
        [-CARRIAGE.rear_w / 2 + 3.5, CARRIAGE.trig_y, CARRIAGE.trig_z]
    )
    return [screw, nut]


def x_carriage_installed() -> Solid:
    """The carriage in its installed position (carriage-local frame)."""
    cuts = _wheel_axle_holes() + _tool_plate_interface() + _top_tab_cutouts()
    cuts += _belt_clamp_cutouts() + _endstop_trigger_cutouts()
    return set_handles(
        _body() - cuts,
        wheel_axles_top=WHEEL_AXLES_TOP,
        wheel_axles_bottom=WHEEL_AXLES_BOTTOM,
        belt_clamps=BELT_CLAMPS,
        trigger_screw=TRIGGER_SCREW,
    )


def x_carriage() -> Solid:
    """The carriage in print orientation: front face down on the bed."""
    return x_carriage_installed().rotate([90, 0, 0]).translate([0, 0, -CARRIAGE.plate_front_y])


# --- FEM definition (carriage-local frame = installed frame) -------------------------
_FRONT_Y = CARRIAGE.plate_front_y
#: The tool plate's face on the carriage (the head hangs here): its weight and knocks enter here
TOOL_FACE = Box(
    lo=(-TOOL_PLATE.w / 2, _FRONT_Y - 0.3, TOOL_PLATE.bottom_z),
    hi=(TOOL_PLATE.w / 2, _FRONT_Y + 0.3, TOOL_PLATE.top_z),
    facing=(0, -1, 0),
)
_FACE_CENTRE: Vec3 = (0.0, _FRONT_Y, (TOOL_PLATE.bottom_z + TOOL_PLATE.top_z) / 2)
#: The tool plate's thickness of carriage behind the face (its displacement tilts the head)
TOOL_PLATE_NODES = Box(
    lo=(-TOOL_PLATE.w / 2, _FRONT_Y - 0.1, TOOL_PLATE.bottom_z),
    hi=(TOOL_PLATE.w / 2, _FRONT_Y + CARRIAGE.plate_t, TOOL_PLATE.top_z),
)
#: Where the belt lies on the rear block's flat top, under each clamp (left, right)
CLAMP_FOOTPRINTS = [
    Box(
        lo=(sx * CLAMP_X - CLAMP.length / 2, X_BELT.y - CLAMP.w / 2, X_BELT.back_z - 0.3),
        hi=(sx * CLAMP_X + CLAMP.length / 2, X_BELT.y + CLAMP.w / 2, X_BELT.back_z + 0.3),
        facing=(0, 0, 1),
    )
    for sx in (-1, 1)
]
#: The wheel axle bolts' heads on the counterbore floors of the front face (top, bottom pairs)
AXLE_SEATS = [
    Cylinder(
        center=(sx * WHEEL_X, _FRONT_Y + CARRIAGE.head_recess, z),
        axis=(0, 1, 0),
        radius=metric(5).washer_od / 2 - 0.3,
        inner_radius=TOL.bolt_hole_d(5) / 2,
        half_length=0.3,
        facing=(0, -1, 0),
    )
    for z in CARRIAGE.wheel_z
    for sx in (-1, 1)
]
#: The pen tip, about 19 mm in front of the carriage face (ASSUMED, middle of 16-22 mm)
_PEN_TIP: Vec3 = (0.0, _FRONT_Y - 19.0, PEN_TIP_Z)


def _arm() -> Vec3:
    """From the middle of the tool-plate face to the pen tip."""
    return (
        _PEN_TIP[0] - _FACE_CENTRE[0],
        _PEN_TIP[1] - _FACE_CENTRE[1],
        _PEN_TIP[2] - _FACE_CENTRE[2],
    )


def _belt_case(name: str, run_n: float, sustained: bool) -> LoadCase:
    """The X belt's two ends pull the rear block apart (and pull on the clamps' footprints)."""
    return LoadCase(
        name,
        f"The belt's two ends, each {run_n:g} N, pull the rear block apart (±x)",
        (
            Force(CLAMP_FOOTPRINTS[0], (-run_n, 0.0, 0.0)),
            Force(CLAMP_FOOTPRINTS[1], (run_n, 0.0, 0.0)),
        ),
        "loads.X_BELT_LOADS",
        sustained=sustained,
    )


def _knock(name: str, direction: Vec3) -> LoadCase:
    """A pen knock: the force at the pen tip moved to the tool-plate face with its couple."""
    force = (direction[0] * PEN_KNOCK, direction[1] * PEN_KNOCK, direction[2] * PEN_KNOCK)
    loads: tuple[Load, ...] = (
        Force(TOOL_FACE, force),
        Moment(TOOL_FACE, lever_couple(_arm(), force)),
    )
    return LoadCase(
        name,
        f"A hand or a curled sheet knocks the pen tip with {PEN_KNOCK:g} N",
        loads,
        "loads.PEN_KNOCK",
    )


_WEIGHT_AND_INERTIA = LoadCase(
    "weight_accel",
    "The tool head's weight and its inertia at peak acceleration (x)",
    (
        Force(
            TOOL_FACE,
            (CARRIAGE_HEAD_KG * ACCELERATION / 1000, 0.0, -CARRIAGE_HEAD_KG * G),
        ),
    ),
    "loads.CARRIAGE_HEAD_KG, loads.ACCELERATION",
)
_OPERATING = ("belt_preload", "belt_peak", "weight_accel")


def _limits(axis_name: str, direction: Vec3) -> DisplacementLimit:
    """The tool plate's allowed movement along an axis under the operating cases."""
    return DisplacementLimit(f"tool_plate_{axis_name}", TOOL_PLATE_NODES, 0.05, direction, _OPERATING)


PART = PrintedPart(
    name="x_carriage",
    description="X carriage: wheels on the beam, belt clamps, tool-plate hook",
    build=x_carriage,
    analysis=x_carriage_installed,
    frame="installed",
    build_direction=(0, 1, 0),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=FemSpec(
        load_cases=(
            _belt_case("belt_preload", X_BELT_LOADS.preload_n, True),
            _belt_case("belt_peak", X_BELT_LOADS.peak_n, False),
            _WEIGHT_AND_INERTIA,
            _knock("pen_knock_x", (1, 0, 0)),
            _knock("pen_knock_y", (0, 1, 0)),
        ),
        supports=tuple(
            Support(f"wheel_axle_{i + 1}", seat, "Wheel axle bolt head seat: fixed")
            for i, seat in enumerate(AXLE_SEATS)
        ),
        displacement_limits=(
            _limits("x", (1, 0, 0)),
            _limits("y", (0, 1, 0)),
            _limits("z", (0, 0, 1)),
        ),
    ),
)
