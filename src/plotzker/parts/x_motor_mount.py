"""X motor mount (STATUS.md T3.4). Print ×1 (right gantry end).

Purpose: holds the X NEMA17 behind the beam at the right end of the gantry, shaft
pointing forward (−y) so the 20T pulley sits on the X belt line. The foot sits on the
right gantry bracket's base over the rear SCS block and is clamped by that block's front
2 × M5 (they become M5×25); the motor body hangs just above the rear row's bolt heads.
A low rib under the motor rests on the base and carries its weight.

  side view (looking along x)          top view
       plate                               ┌─motor─┐
  pulley │┌──────┐                    beam │       │
  ◯═════ ││ motor│                    ═════│plate  │
         │└──────┘                         ├──rib──┤
  ───foot┴──rib───  on the bracket base    └─foot──┘

Frame: designed in the LEFT bracket-local frame (``params.XDrive``), z = 0 on the SCS
top face (:func:`x_motor_mount_left`). The printed part is the mirror image (it goes
on the right end): :func:`x_motor_mount`.

Hardware: 4 × M3×10 ISO 4762 (motor); 2 × M5×25 ISO 4762 replacing the rear SCS bolts
of the right bracket's front row; 20T GT2 pulley on the motor (hub toward the motor, belt center
at the X belt line — slide it on the shaft to align with the idler).
Print: default profile (``profiles/default.toml``); foot down; no supports.

FEM: the motor's belt pull, weight and stall torque act on the plate's motor face; the foot is
held by the front M5 heads and rests on the bracket's base; see :data:`PART`.
"""

from typing import TYPE_CHECKING

from cadder.geometry import EPS, FN_HOLE, teardrop_y
from cadder.handles import handle, set_handles
from cadder.hardware import NEMA17, SCS10UU, metric
from cadder.part import DisplacementLimit, FemSpec, LoadCase, PrintedPart, Support
from cadder.regions import Box, Cylinder, bond_zone
from cadder.types import Matrix
from pythonscad import cube, cylinder

from plotzker.loads import X_BELT_LOADS
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import BRACKET, TOL, X_BELT, X_DRIVE, Y_AXIS
from plotzker.parts.motor_fem import motor_loads

if TYPE_CHECKING:
    from pythonscad import Solid

AXIS_Z = X_BELT.pulley_axis_z - Y_AXIS.scs_top_z  #: motor axis, local z
FOOT_Z0 = BRACKET.base_t  #: the foot sits on the bracket base
PLATE_X = (X_DRIVE.motor_x - NEMA17.width / 2, X_DRIVE.motor_x + NEMA17.width / 2)
PLATE_TOP = AXIS_Z + NEMA17.width / 2
#: The foot's x extent (under the SCS block and the plate)
FOOT_X = (min(-SCS10UU.width / 2 - 1, PLATE_X[0]), max(SCS10UU.width / 2, PLATE_X[1]))
MOTOR_BOTTOM = AXIS_Z - NEMA17.width / 2
#: Motor: its face on the plate's front face, shaft axis along -y toward the beam
MOTOR: Matrix = handle([X_DRIVE.motor_x, X_DRIVE.motor_face_y, AXIS_Z], [90, 0, 0])
#: Pulley: hub on the shaft
PULLEY: Matrix = handle([X_DRIVE.motor_x, X_DRIVE.pulley_hub_y, AXIS_Z], [90, 0, 0])
#: The 4 motor M3 screws: heads on the plate's beam side (rear face), shanks toward +y
MOTOR_SCREWS: list[Matrix] = [
    handle(
        [
            X_DRIVE.motor_x + dx * NEMA17.hole_pitch / 2,
            X_DRIVE.plate_y0,
            AXIS_Z + dz * NEMA17.hole_pitch / 2,
        ],
        [90, 0, 0],
    )
    for dx in (-1, 1)
    for dz in (-1, 1)
]


def x_motor_mount_left() -> Solid:
    """The mount as designed, in the left bracket-local frame (not printed like this)."""
    d = X_DRIVE
    foot_x0, foot_x1 = FOOT_X
    foot = cube([foot_x1 - foot_x0, d.motor_foot_y[1] - d.motor_foot_y[0], d.foot_t]).translate(
        [foot_x0, d.motor_foot_y[0], FOOT_Z0]
    )
    plate = cube([NEMA17.width, d.motor_plate_t, PLATE_TOP - FOOT_Z0]).translate(
        [PLATE_X[0], d.plate_y0, FOOT_Z0]
    )
    rib = cube(
        [d.motor_rib_t, d.foot_y[1] - d.motor_face_y + EPS, MOTOR_BOTTOM - 0.5 - FOOT_Z0]
    ).translate([d.motor_x - d.motor_rib_t / 2, d.motor_face_y - EPS, FOOT_Z0])
    bolts = [
        cylinder(d=TOL.bolt_hole_d(5), h=d.foot_t + 2, fn=FN_HOLE).translate(
            [hx * SCS10UU.hole_pitch_x / 2, y, FOOT_Z0 - 1]
        )
        for hx in (-1, 1)
        for y in d.bolt_rows[:1]
    ]
    recess = [
        cylinder(d=TOL.slide_d(metric(5).head_d), h=d.foot_head_recess + 1, fn=FN_HOLE).translate(
            [hx * SCS10UU.hole_pitch_x / 2, y, FOOT_Z0 + d.foot_t - d.foot_head_recess]
        )
        for hx in (-1, 1)
        for y in d.bolt_rows[:1]
    ]
    plate_mid_y = d.plate_y0 + d.motor_plate_t / 2
    boss = teardrop_y(NEMA17.boss_d + 0.4, d.motor_plate_t + 2).translate(
        [d.motor_x, plate_mid_y, AXIS_Z]
    )
    screws = [
        teardrop_y(TOL.bolt_hole_d(3), d.motor_plate_t + 2).translate(
            [
                d.motor_x + dx * NEMA17.hole_pitch / 2,
                plate_mid_y,
                AXIS_Z + dz * NEMA17.hole_pitch / 2,
            ]
        )
        for dx in (-1, 1)
        for dz in (-1, 1)
    ]
    mount = (foot | plate | rib) - bolts - recess - boss - screws
    return set_handles(mount, motor=MOTOR, pulley=PULLEY, motor_screws=MOTOR_SCREWS)


def x_motor_mount() -> Solid:
    """The printed part (right end) = mirror image, foot on the bed."""
    return x_motor_mount_left().mirror([1, 0, 0]).translate([0, 0, -FOOT_Z0])


# --- FEM definition (left bracket-local frame = installed frame) --------------------
#: Pulley belt center, and the motor's seat on the plate (the motor presses on the plate's back)
PULLEY_POINT = (X_DRIVE.motor_x, X_BELT.y, AXIS_Z)
FACE_POINT = (X_DRIVE.motor_x, X_DRIVE.motor_face_y, AXIS_Z)
MOTOR_FACE = Box(
    lo=(X_DRIVE.motor_x - NEMA17.width / 2, X_DRIVE.motor_face_y - 0.3, AXIS_Z - NEMA17.width / 2),
    hi=(X_DRIVE.motor_x + NEMA17.width / 2, X_DRIVE.motor_face_y + 0.3, AXIS_Z + NEMA17.width / 2),
    facing=(0, 1, 0),
)
#: The front row's M5 heads in their recesses (the rear row's bolts don't pass the foot)
BOLT_SEATS = [
    Cylinder(
        center=(
            hx * SCS10UU.hole_pitch_x / 2,
            X_DRIVE.bolt_rows[0],
            FOOT_Z0 + X_DRIVE.foot_t - X_DRIVE.foot_head_recess,
        ),
        axis=(0, 0, 1),
        radius=metric(5).head_d / 2,
        inner_radius=TOL.bolt_hole_d(5) / 2,
        half_length=0.3,
        facing=(0, 0, 1),
    )
    for hx in (-1, 1)
]
FOOT_BEARING = Box(
    lo=(FOOT_X[0], X_DRIVE.motor_foot_y[0], FOOT_Z0 - 0.3),
    hi=(FOOT_X[1], X_DRIVE.motor_foot_y[1], FOOT_Z0 + 0.3),
    facing=(0, 0, -1),
)


#: Friction around each front bolt: the foot's underside is bonded to the bracket within BOND_RADIUS
BOND_ZONES = [
    bond_zone((hx * SCS10UU.hole_pitch_x / 2, X_DRIVE.bolt_rows[0], FOOT_Z0)) for hx in (-1, 1)
]


def _case(name: str, jam: bool) -> LoadCase:
    """Belt pull (toward the idler: +x in this frame), weight and, at a jam, the stall torque."""
    return LoadCase(
        name,
        "Two belt runs pull the pulley inboard (+x); the motor's weight; "
        + ("a jam adds the stall torque and the peak run tension" if jam else "preload tension"),
        tuple(
            motor_loads(
                MOTOR_FACE, X_BELT_LOADS, jam, PULLEY_POINT, FACE_POINT, (1, 0, 0), (0, -1, 0)
            )
        ),
        "loads.X_BELT_LOADS, loads.MOTOR_LOADS",
        sustained=not jam,
    )


PART = PrintedPart(
    name="x_motor_mount",
    description="X motor mount: plate for the NEMA17 (designed in the left bracket frame)",
    build=x_motor_mount,
    analysis=x_motor_mount_left,
    frame="installed",
    build_direction=(0, 0, 1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=FemSpec(
        load_cases=(_case("belt_preload", False), _case("belt_peak", True)),
        supports=(
            Support("front_bolt_a", BOLT_SEATS[0], "Front M5 head, -x side: recess floor, fixed"),
            Support("front_bolt_b", BOLT_SEATS[1], "Front M5 head, +x side: recess floor, fixed"),
            Support(
                "foot_bearing",
                FOOT_BEARING,
                "Foot resting on the bracket's base: held in z",
                constrain=(False, False, True),
            ),
            Support("front_bolt_zone_a", BOND_ZONES[0], "Friction round the -x front bolt: bonded"),
            Support("front_bolt_zone_b", BOND_ZONES[1], "Friction round the +x front bolt: bonded"),
        ),
        displacement_limits=(
            DisplacementLimit("motor_face_along_belt", MOTOR_FACE, 0.3, (1, 0, 0)),
            DisplacementLimit("motor_face_sideways", MOTOR_FACE, 0.1, (0, 1, 0)),
            DisplacementLimit("motor_face_vertical", MOTOR_FACE, 0.1, (0, 0, 1)),
        ),
    ),
)
