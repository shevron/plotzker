"""X carriage on the upright 4020 beam (STATUS.md T3.3). Print ×1.

Purpose: carries the tool head. Four V-wheels ride the beam's top and bottom grooves
(bottom pair on eccentric spacers for preload, D21). A bridge over the middle of the
beam reaches a rear block that clamps both ends of the X belt (vertical loop behind
the beam) and carries the X endstop trigger. The front face has the tool-plate
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
  4 × M5×35 ISO 4762 + 4 × M5 washers (front) + 4 × M5 nuts (nyloc preferred)
  2 × M3 nuts (pressed in from the bottom edge) — tool-plate clamp screws (tool head
      supplies the M3 screws)
  4 × M3 nuts (pressed in from the back) + 4 × M3×14 ISO 4762 + 2 × belt_clamp (printed) — X belt
  1 × M3×16 ISO 4762 + 2 × M3 nuts — X endstop trigger: screwed into the rear block's
      left end through a captive nut; its head touches the switch; lock nut outside
  zip ties for the tool-head cable

Print: PETG (preferred) or PLA; 0.2 mm layers; 4 perimeters; 40 % infill; front face
down on the bed; no supports (hook groove and side holes are self-supporting:
45° walls, short bridges, teardrops).
"""

from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull, linear_extrude, polygon

from plotter_cad.geometry import EPS, FN_HOLE, Matrix, handle, set_handles, teardrop_x
from plotter_cad.hardware import ECCENTRIC, VWHEEL
from plotter_cad.params import BEAM, CARRIAGE, CLAMP, TOL, TOOL_PLATE, X_BELT

if TYPE_CHECKING:
    from pythonscad import Solid

WHEEL_X = CARRIAGE.wheel_pitch_x / 2  #: wheel axle x (±)
REAR_Y0 = BEAM.depth / 2 + 0.5  #: rear block front face (behind the beam)
REAR_Y1 = X_BELT.y + CLAMP.w / 2 + 1  #: rear block back face
WIDEN_Y = VWHEEL.width / 2 + 1  #: the bridge may widen behind the top wheels
CLAMP_X = CARRIAGE.rear_w / 2 - CLAMP.length / 2  #: X belt clamp centers (±)

#: Wheel axle bolts (top pair, bottom pair): on the plate's front face, along +y into the plate
WHEEL_AXLES_TOP = [
    handle([sx * WHEEL_X, CARRIAGE.plate_front_y, CARRIAGE.wheel_z[0]], [90, 0, 0])
    for sx in (-1, 1)
]
WHEEL_AXLES_BOTTOM = [
    handle([sx * WHEEL_X, CARRIAGE.plate_front_y, CARRIAGE.wheel_z[1]], [90, 0, 0])
    for sx in (-1, 1)
]
#: X belt clamps (left, right): on the rear block's flat underside, belt center, running along x
BELT_CLAMPS = [
    handle([sx * CLAMP_X + CLAMP.length / 2, X_BELT.y, CARRIAGE.bridge_z], [0, 0, 90])
    for sx in (-1, 1)
]
#: X endstop trigger screw: on the rear block's left end, along +x into the block
TRIGGER_SCREW: Matrix = handle(
    [-CARRIAGE.rear_w / 2, CARRIAGE.trig_y, CARRIAGE.trig_z], [0, -90, 0]
)


def _body() -> Solid:
    """Carriage solid before the holes and cutouts."""
    c = CARRIAGE
    plate = cube([c.plate_w, c.plate_t, c.top_z - c.bottom_z]).translate(
        [-c.plate_w / 2, c.plate_front_y, c.bottom_z]
    )
    tab = cube([c.tab_w, c.plate_t, c.tab_h + EPS]).translate(
        [-c.tab_w / 2, c.plate_front_y, c.top_z - EPS]
    )
    standoffs = [
        cylinder(d=c.top_boss_d, h=ECCENTRIC.stack + EPS, fn=32)
        .rotate([-90, 0, 0])
        .translate([sx * WHEEL_X, c.plate_back_y - EPS, c.wheel_z[0]])
        for sx in (-1, 1)
    ]
    bridge = cube([c.bridge_w, REAR_Y0 - c.plate_back_y + EPS, c.bridge_h]).translate(
        [-c.bridge_w / 2, c.plate_back_y - EPS, c.bridge_z]
    )
    # widening (45°) from the bridge into the rear block, behind the wheels
    widening = hull(
        cube([c.bridge_w, EPS, c.rear_h]).translate([-c.bridge_w / 2, WIDEN_Y, c.bridge_z]),
        cube([c.rear_w, EPS, c.rear_h]).translate(
            [-c.rear_w / 2, WIDEN_Y + (c.rear_w - c.bridge_w) / 2, c.bridge_z]
        ),
    )
    rear = cube([c.rear_w, REAR_Y1 - REAR_Y0, c.rear_h]).translate(
        [-c.rear_w / 2, REAR_Y0, c.bridge_z]
    )
    return plate | tab | standoffs | bridge | widening | rear


def _wheel_axle_holes() -> list[Solid]:
    """Wheel axle holes."""
    c = CARRIAGE
    holes = []
    for sx in (-1, 1):
        # top wheels: M5 clearance through plate and stand-off
        holes.append(
            cylinder(d=TOL.bolt_hole_d(5), h=c.plate_t + ECCENTRIC.stack + 2, fn=FN_HOLE)
            .rotate([-90, 0, 0])
            .translate([sx * WHEEL_X, c.plate_front_y - 1, c.wheel_z[0]])
        )
        # bottom wheels: hole for the eccentric boss (the M5 moves ±offset inside it)
        holes.append(
            cylinder(d=TOL.slide_d(ECCENTRIC.boss_d), h=c.plate_t + 2, fn=FN_HOLE)
            .rotate([-90, 0, 0])
            .translate([sx * WHEEL_X, c.plate_front_y - 1, c.wheel_z[1]])
        )
    return holes


def _tool_plate_interface() -> list[Solid]:
    """Tool-plate hook groove and mounting holes."""
    c, tp = CARRIAGE, TOOL_PLATE
    # hook groove (French cleat): opening hook_h tall at the face, undercut hook_d
    # downward at 45°; closed ends locate the tool plate in X
    profile = polygon(
        [
            [-1, tp.top_z],
            [tp.hook_d, tp.top_z],
            [tp.hook_d, tp.top_z - tp.hook_h - tp.hook_d],
            [0, tp.top_z - tp.hook_h],
            [-1, tp.top_z - tp.hook_h],
        ]
    )
    groove = (
        linear_extrude(profile, height=tp.w + 2 * tp.fit_gap, center=True)
        .rotate([90, 0, 90])
        .translate([0, c.plate_front_y, 0])
    )
    # M3 clearance holes through the plate; each nut is pressed into a slot from the bottom
    # edge, behind a wall on the front side that takes the pull of the tool plate's screws
    af, ac, nut_t = TOL.nut_trap_af(3), TOL.nut_trap_ac(3), TOL.nut_trap_h(3)
    screw_zc = tp.bottom_z + tp.screw_z
    nuts = []
    for sx in (-1, 1):
        x = sx * tp.screw_pitch / 2
        nuts.append(
            cylinder(d=TOL.bolt_hole_d(3), h=c.plate_t + 2, fn=FN_HOLE)
            .rotate([-90, 0, 0])
            .translate([x, c.plate_front_y - 1, screw_zc])
        )
        nuts.append(
            cube([af, nut_t, screw_zc + ac / 2 - tp.bottom_z + 1]).translate(
                [x - af / 2, c.plate_front_y + TOL.nut_wall, tp.bottom_z - 1]
            )
        )
    return [groove, *nuts]


def _top_tab_cutouts() -> list[Solid]:
    """Windows for the top connector tabs."""
    c, (conn_w, conn_h) = CARRIAGE, TOOL_PLATE.conn_size
    window = cube([conn_w, c.plate_t + 2, conn_h]).translate(
        [-conn_w / 2, c.plate_front_y - 1, c.top_z + c.tab_h - 3 - conn_h]
    )
    slot_w, slot_h = c.zip_slot
    zip_slots = [
        cube([slot_w, c.plate_t + 2, slot_h]).translate(
            [
                sx * (conn_w / 2 + 1 + slot_w / 2) - slot_w / 2,
                c.plate_front_y - 1,
                c.top_z - 2 - slot_h,
            ]
        )  # above the bridge
        for sx in (-1, 1)
    ]
    return [window, *zip_slots]


def _belt_clamp_cutouts() -> list[Solid]:
    """Belt clamp screw holes and nut slots (the rear block's underside is flat)."""
    c = CARRIAGE
    af, ac, nut_t = TOL.nut_trap_af(3), TOL.nut_trap_ac(3), TOL.nut_trap_h(3)
    cuts = []
    for sx in (-1, 1):
        x = sx * CLAMP_X
        holes = [
            cylinder(d=TOL.bolt_hole_d(3), h=CLAMP.nut_z + 1, fn=FN_HOLE).translate(
                [x, X_BELT.y + sy * CLAMP.screw_dx, c.bridge_z - EPS]
            )
            for sy in (-1, 1)
        ]
        # one slot from the back face takes both nuts (flat on the floor, pressed in)
        y0 = X_BELT.y - CLAMP.screw_dx - ac / 2
        slot = cube([af, REAR_Y1 + 1 - y0, nut_t]).translate(
            [x - af / 2, y0, c.bridge_z + CLAMP.nut_z]
        )
        cuts += [*holes, slot]
    return cuts


def _endstop_trigger_cutouts() -> list[Solid]:
    """M3 along -x from the rear block's left end, through a captive nut."""
    c = CARRIAGE
    screw = (
        teardrop_x(TOL.bolt_hole_d(3), 18)
        .rotate([-90, 0, 0])
        .translate([-c.rear_w / 2 + 8, c.trig_y, c.trig_z])
    )
    nut_t = TOL.nut_trap_h(3)
    nut = cube([nut_t, TOL.nut_trap_af(3), c.rear_h]).translate(
        [
            -c.rear_w / 2 + 3.5 - nut_t / 2,
            c.trig_y - TOL.nut_trap_af(3) / 2,
            c.trig_z - TOL.nut_trap_ac(3) / 2,
        ]
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
