"""Y motor mount (STATUS.md T3.5). Print ×1 left + ×1 right (mirror image).

Purpose: holds a Y NEMA17 on the baseboard behind the rear SK10, with its shaft pointing
outboard so the 20T pulley sits on the Y belt line (30 mm outboard of the shaft). The
plate carries the motor face; the foot (screwed to the baseboard) extends outboard,
where the screws stay accessible with the motor fitted.

  top view (left side)                      side view (looking along +x)
  belt ═◯pulley┃plate┃ motor body →         ┌─────────┐
        ═══════╋     ┃ (inboard)            │ ◯ motor │ plate
  ─ foot ──────┸─────┘                      └─────────┘ ← gussets at both ends
                                            ──── foot (2 × 4×25 countersunk wood screws)

Frame: left side frame (``params.YDrive``: x from the shaft, machine y, z = baseboard
top); the part is printed foot down in the same orientation. The right-hand part is the
mirror image (:func:`y_motor_mount`).

Hardware: 4 × M3×10 ISO 4762 (motor, from the pulley side); 20T GT2 pulley on the motor
(hub toward the motor, belt center on the belt line); 2 × 4×25 countersunk wood screws
into the baseboard (through 9 mm bosses on the foot).
Print: default profile (``profiles/default.toml``); foot down; no supports.

FEM (left; the right is the mirror image): the motor's belt pull, weight and stall torque act on
the plate's motor face; held by the two wood screws and the baseboard; see :data:`PART_LEFT`.
"""

from typing import TYPE_CHECKING

from cadder.geometry import EPS, teardrop_x
from cadder.handles import handle, set_handles
from cadder.hardware import NEMA17
from cadder.part import DisplacementLimit, FemSpec, LoadCase, PrintedPart, Support
from cadder.regions import Box, Cylinder, bond_zone
from cadder.types import Matrix
from pythonscad import cube, hull

from plotzker.loads import Y_BELT_LOADS
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import TOL, WOOD_SCREW, Y_AXIS, Y_DRIVE
from plotzker.parts.motor_fem import motor_loads
from plotzker.parts.sk10_pocket import PocketEnd, sk10_pocket
from plotzker.parts.wood_screw import wood_screw_boss, wood_screw_hole
from plotzker.types import Side

if TYPE_CHECKING:
    from pythonscad import Solid

AXIS_Z = Y_AXIS.pulley_axis_z  #: motor axis height
SCREW_INSET = WOOD_SCREW.boss_d / 2 + 0.5  #: foot screws from the plate ends (y)

#: Motor mounting screws: on the plate's outboard face (the pulley side), axis along +x
MOTOR_SCREWS = [
    handle(
        [
            Y_DRIVE.motor_plate_x[0],
            Y_DRIVE.motor_y + dy * NEMA17.hole_pitch / 2,
            AXIS_Z + dz * NEMA17.hole_pitch / 2,
        ],
        [0, -90, 0],
    )
    for dy in (-1, 1)
    for dz in (-1, 1)
]
#: Motor: its face on the plate's inboard face, shaft axis along -x (outboard)
MOTOR: Matrix = handle([Y_DRIVE.motor_plate_x[1], Y_DRIVE.motor_y, AXIS_Z], [0, -90, 0])
#: Pulley: hub on the shaft just outboard of the plate, same axis
PULLEY: Matrix = handle([Y_DRIVE.pulley_hub_x, Y_DRIVE.motor_y, AXIS_Z], [0, -90, 0])


def y_motor_mount_installed() -> Solid:
    """The mount in the left side frame."""
    d = Y_DRIVE
    x0, x1 = d.motor_plate_x
    y0, y1 = d.motor_plate_y
    foot = cube([x1 - d.motor_foot_x0, y1 - y0, d.foot_t]).translate([d.motor_foot_x0, y0, 0])
    pocket_frame, pocket_cut = sk10_pocket(PocketEnd.REAR, d.motor_foot_x0)
    plate = cube([x1 - x0, y1 - y0, d.motor_top_z]).translate([x0, y0, 0])
    gussets = [
        hull(
            cube([d.gusset_len, d.gusset_t, EPS]).translate([x0 - d.gusset_len, y, d.foot_t - EPS]),
            cube([EPS, d.gusset_t, d.gusset_len]).translate([x0 - EPS, y, d.foot_t]),
        )
        for y in (y0, y1 - d.gusset_t)
    ]
    plate_cx = (x0 + x1) / 2
    boss = teardrop_x(NEMA17.boss_d + 0.4, d.motor_plate_t + 2).translate(
        [plate_cx, d.motor_y, AXIS_Z]
    )
    screws = [
        teardrop_x(TOL.bolt_hole_d(3), d.motor_plate_t + 2).translate(
            [plate_cx, screw[1][3], screw[2][3]]
        )
        for screw in MOTOR_SCREWS
    ]
    foot_x = d.motor_foot_x0 + WOOD_SCREW.boss_d / 2
    screw_ys = (y0 + SCREW_INSET, y1 - SCREW_INSET)
    bosses = [wood_screw_boss(foot_x, y) for y in screw_ys]
    holes = [wood_screw_hole(foot_x, y) for y in screw_ys]
    foot = foot | bosses[0] | bosses[1]
    mount = (foot | plate | gussets | pocket_frame) - pocket_cut - boss - screws - holes
    return set_handles(mount, motor_screws=MOTOR_SCREWS, motor=MOTOR, pulley=PULLEY)


def y_motor_mount(side: Side = Side.LEFT) -> Solid:
    """The mount for one side, in print orientation (the right one is mirrored)."""
    mount = y_motor_mount_installed()
    return mount.mirror([1, 0, 0]) if side is Side.RIGHT else mount


# --- FEM definition (left side frame = installed frame) ---------------------------------
_X0, _X1 = Y_DRIVE.motor_plate_x
_Y0, _Y1 = Y_DRIVE.motor_plate_y
#: Pulley belt center, and the motor's seat on the plate (the motor presses on the inboard face)
PULLEY_POINT = (Y_AXIS.belt_x, Y_DRIVE.motor_y, AXIS_Z)
FACE_POINT = (_X1, Y_DRIVE.motor_y, AXIS_Z)
MOTOR_FACE = Box(
    lo=(_X1 - 0.3, Y_DRIVE.motor_y - NEMA17.width / 2, AXIS_Z - NEMA17.width / 2),
    hi=(_X1 + 0.3, Y_DRIVE.motor_y + NEMA17.width / 2, AXIS_Z + NEMA17.width / 2),
    facing=(1, 0, 0),
)
_FOOT_X = Y_DRIVE.motor_foot_x0 + WOOD_SCREW.boss_d / 2
_SCREW_YS = (_Y0 + SCREW_INSET, _Y1 - SCREW_INSET)
SCREW_SEATS = [
    Cylinder(
        center=(_FOOT_X, y, WOOD_SCREW.boss_t - WOOD_SCREW.sink_h / 2),
        axis=(0, 0, 1),
        radius=WOOD_SCREW.sink_d / 2,
        inner_radius=WOOD_SCREW.hole_d / 2,
        half_length=WOOD_SCREW.sink_h / 2 + 0.3,
        facing=(0, 0, 1),
        facing_tol_deg=60,
    )
    for y in _SCREW_YS
]
FOOT_BEARING = Box(lo=(Y_DRIVE.motor_foot_x0, _Y0, -0.3), hi=(_X1, _Y1, 0.3), facing=(0, 0, -1))


#: Friction around each wood screw: the foot's underside is bonded to the baseboard
BOND_ZONES = [bond_zone((_FOOT_X, y, 0.0)) for y in _SCREW_YS]


def _case(name: str, jam: bool) -> LoadCase:
    """Belt pull (toward the idler: -y), weight and, at a jam, the stall torque."""
    return LoadCase(
        name,
        "Two belt runs pull the pulley forward (-y); the motor's weight; "
        + ("a jam adds the stall torque and the peak run tension" if jam else "preload tension"),
        tuple(
            motor_loads(
                MOTOR_FACE, Y_BELT_LOADS, jam, PULLEY_POINT, FACE_POINT, (0, -1, 0), (-1, 0, 0)
            )
        ),
        "loads.Y_BELT_LOADS, loads.MOTOR_LOADS",
        sustained=not jam,
    )


PART_LEFT = PrintedPart(
    name="y_motor_mount_left",
    description="Y motor mount (left): plate for the NEMA17 behind the rear SK10",
    build=lambda: y_motor_mount(Side.LEFT),
    analysis=y_motor_mount_installed,
    frame="installed",
    build_direction=(0, 0, 1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=FemSpec(
        load_cases=(_case("belt_preload", False), _case("belt_peak", True)),
        supports=(
            Support("wood_screw_front", SCREW_SEATS[0], "Front wood screw: countersink, fixed"),
            Support("wood_screw_rear", SCREW_SEATS[1], "Rear wood screw: countersink, fixed"),
            Support(
                "foot_bearing",
                FOOT_BEARING,
                "Foot resting on the baseboard: held in z",
                constrain=(False, False, True),
            ),
            Support("screw_zone_front", BOND_ZONES[0], "Friction round the front screw: bonded"),
            Support("screw_zone_rear", BOND_ZONES[1], "Friction round the rear screw: bonded"),
        ),
        displacement_limits=(
            DisplacementLimit("motor_face_along_belt", MOTOR_FACE, 0.3, (0, 1, 0)),
            DisplacementLimit("motor_face_sideways", MOTOR_FACE, 0.1, (1, 0, 0)),
            DisplacementLimit("motor_face_vertical", MOTOR_FACE, 0.1, (0, 0, 1)),
        ),
    ),
)
PART_RIGHT = PrintedPart(
    name="y_motor_mount_right",
    description="Y motor mount (right): mirror image of the left one",
    build=lambda: y_motor_mount(Side.RIGHT),
    analysis=lambda: y_motor_mount_installed().mirror([1, 0, 0]),
    frame="installed",
    build_direction=(0, 0, 1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    mirror_of="y_motor_mount_left",
)
