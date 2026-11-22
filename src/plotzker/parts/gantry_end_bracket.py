"""Y-gantry end bracket (STATUS.md T3.2). Print ×1 left + ×1 right (mirror image).

Purpose: joins the two SCS10UU blocks on one Y shaft into a rigid gantry end,
carries the X beam (4020 upright) with its bottom 24.5 mm above the blocks, clamps
both ends of that side's Y belt, and carries the adjustable Y-endstop trigger.

  side view (looking along +x, inboard)        top view (left bracket)
           ┌─┐ face plate                     y+ ┌────────────┐ ← rear belt clamp
    beam → │▓│ (2 × M5 into the                  │  ▢      ▢  │   (outboard)
           │▓│  beam end bores)                  │  ┃face     │
      ribs╱│ │                                   │ ═╋══ beam →│  notch: carriage
    ┌────────────────┐ base on 2 × SCS10UU       │  ┃         │  passes here
    └─[SCS]────[SCS]─┘                           │  ▢      ▢  │
                                              y- └[trig]──────┘ ← front belt clamp

Frame: bracket-local (see ``params.GantryBracket``): origin on the SCS top-face plane
over the shaft axis, midway between the blocks; +x inboard, +y back, +z up.
Modeled in print orientation (base on the bed).

Hardware per bracket:
  8 × M5×20 ISO 4762 — base to the two SCS10UU blocks (10 mm thread engagement of 12)
  2 × M5×20 ISO 4762 — face plate into the beam end. The 4020's center bores (Ø4.2)
                       are tapped M5
  4 × M3 nuts (pressed into the hex shafts from the top) + 4 × M3×14 ISO 4762 — two Y belt
                       clamps
  2 × belt_clamp (printed)
  1 × M3×16 ISO 4762 + 2 × M3 nuts — Y endstop trigger (adjust, then lock)
  Right bracket only: 2 × M3 nuts (pressed into slots from the outboard edge) for the loom
                       anchor (``loom_anchor.py``); the left bracket has no such holes
Left bracket only: the X idler's tower (``X_IDLER``): a plate with two side walls on a shelf that
reaches out under it; the idler slider is tied to the tower by its tension screw (T3.22)

Print: default profile (``profiles/default.toml``); base face down; no supports (horizontal
holes are teardrops; the underside is flat).

FEM (left bracket): the X belt's reaction (the tension screw's head pushes the tower +x at the
axle's height, the beam pushes back on the face plate) and the Y belt ends pulling the clamps
apart; held by the 8 block bolts; see :data:`PART`.
"""

from typing import TYPE_CHECKING

from cadder.geometry import EPS, FN_HOLE, teardrop_x, teardrop_y
from cadder.handles import handle, set_handles
from cadder.hardware import SCS10UU, VSLOT, metric
from cadder.part import (
    DisplacementLimit,
    FemSpec,
    Force,
    Load,
    LoadCase,
    PrintedPart,
    Support,
)
from cadder.printing import nut_slot
from cadder.regions import Box, Cylinder, Placement
from cadder.types import Matrix, Vec3
from pythonscad import cube, cylinder, hull

from plotzker.loads import X_BELT_LOADS, Y_BELT_LOADS
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import BEAM, BRACKET, CLAMP, LOOM, TOL, X_DRIVE, X_IDLER, Y_AXIS
from plotzker.parts.floating_idler import head_load, tower, tower_limits
from plotzker.parts.motor_fem import motor_loads
from plotzker.parts.x_motor_mount import FOOT_X
from plotzker.parts.x_motor_mount import PULLEY_POINT as MOTOR_PULLEY
from plotzker.types import Side

if TYPE_CHECKING:
    from pythonscad import Solid


# --- derived local geometry ----------------------------------------------------
BEAM_BOTTOM = BEAM.bottom_z - Y_AXIS.scs_top_z  #: beam bottom, local z (24.5)
FACE_IN_X = BEAM.end_offset + BRACKET.recess  #: inboard face of the face plate
FACE_OUT_X = FACE_IN_X - BRACKET.face_t  #: outboard face (bolt heads)
FACE_TOP = BEAM_BOTTOM + BEAM.height + BRACKET.face_above
#: Beam end bore heights (local z)
BEAM_BOLT_Z = (BEAM_BOTTOM + VSLOT.unit / 2, BEAM_BOTTOM + 3 * VSLOT.unit / 2)


def _block_bolts(block: int) -> list[Matrix]:
    """Handles of one SCS block's 4 bolts: on the base top, bolt axis along z (head up)."""
    return [
        handle(
            [
                hx * SCS10UU.hole_pitch_x / 2,
                block * Y_AXIS.scs_pitch / 2 + hy * SCS10UU.hole_pitch_y / 2,
                BRACKET.base_t,
            ]
        )
        for hx in (-1, 1)
        for hy in (-1, 1)
    ]


#: Bolt handles of the front (-y) and rear (+y) SCS block
BLOCK_BOLTS_FRONT = _block_bolts(-1)
BLOCK_BOLTS_REAR = _block_bolts(1)
#: Beam bolts: on the outboard face, axis along +x (heads outboard)
BEAM_BOLTS = [handle([FACE_OUT_X, 0, z], [0, -90, 0]) for z in BEAM_BOLT_Z]
#: Belt clamps (front, rear): on the flat underside, belt center, clamp start, running +y
BELT_CLAMPS = [
    handle([Y_AXIS.belt_x, y0, 0]) for y0 in (-BRACKET.len_y / 2, BRACKET.len_y / 2 - CLAMP.length)
]
#: Loom anchor screws (right bracket): on the base top, axis along z (head up)
LOOM_ANCHOR = [handle([LOOM.anchor_screw_x, y, BRACKET.base_t]) for y in LOOM.anchor_screw_y]
#: Y endstop trigger screw: head behind the boss, axis along +y (tip forward, -y)
TRIGGER_SCREW = handle(
    [BRACKET.trig_x, -BRACKET.len_y / 2 + BRACKET.trig_boss[1], BRACKET.trig_z], [-90, 0, 0]
)


def _tower() -> Solid:
    """The X idler's tower (:func:`floating_idler.tower`): a plate with the tension screw's head
    seat on its outer face and two walls along the slider's sides, standing on the shelf."""
    return tower(X_IDLER).translate([X_IDLER.tower_s0, X_IDLER.belt_pos, 0])


def _body(side: Side) -> Solid:
    """Bracket solid before the holes and cutouts."""
    b = BRACKET
    base = cube([b.x_in - b.x_out, b.len_y, b.base_t]).translate([b.x_out, -b.len_y / 2, 0])
    if side is Side.LEFT:
        # shelf under the X idler's tower (T3.19, T3.22)
        y0, y1 = b.shelf_y
        base = base | cube([b.x_out - b.shelf_x + EPS, y1 - y0, b.base_t]).translate(
            [b.shelf_x, y0, 0]
        )
        base = base | _tower()
    face = cube([b.face_t, b.face_y[1] - b.face_y[0], FACE_TOP]).translate(
        [FACE_OUT_X, b.face_y[0], 0]
    )
    # ribs: wedges from the face plate down to the outboard edge of the base
    ribs = [
        hull(
            cube([EPS, b.rib_t, FACE_TOP]).translate([FACE_OUT_X - EPS, y0, 0]),
            cube([EPS, b.rib_t, b.base_t]).translate([b.x_out, y0, 0]),
        )
        for y0 in b.rib_y0
    ]
    bx, by, bz = b.trig_boss
    boss = cube([bx, by, bz + EPS]).translate([b.trig_x - bx / 2, -b.len_y / 2, b.base_t - EPS])
    return base | face | ribs | boss


def _loom_cutouts() -> list[Solid]:
    """M3 holes from the top and nut slots from the outboard edge for the loom anchor."""
    nut_t = TOL.nut_trap_h(3)
    top = BRACKET.base_t - TOL.nut_wall  #: plastic above the nut takes the pull
    cuts = []
    for h in LOOM_ANCHOR:
        x, y = h[0][3], h[1][3]
        cuts.append(
            cylinder(d=TOL.bolt_hole_d(3), h=BRACKET.base_t, fn=FN_HOLE).translate([x, y, 0])
        )
        cuts.append(
            nut_slot(3, x - BRACKET.x_out + 1, "z", "-x", tol=TOL).translate(
                [x, y, top - nut_t / 2]
            )
        )
    return cuts


def _cutouts() -> list[Solid]:
    """Holes and pockets subtracted from the body."""
    b = BRACKET
    cuts = []
    # carriage notch: between the blocks the base stops at the face plate
    cuts.append(cube([b.x_in, 2 * b.notch_y, b.base_t + 2]).translate([FACE_IN_X, -b.notch_y, -1]))
    cuts += [
        cylinder(d=TOL.bolt_hole_d(5), h=b.base_t + 2, fn=FN_HOLE)
        .translate([0, 0, -b.base_t - 1])
        .align(bolt)
        for bolt in (*BLOCK_BOLTS_FRONT, *BLOCK_BOLTS_REAR)
    ]
    clr = TOL.slide
    cuts.append(
        cube([b.recess + 1, BEAM.depth + 2 * clr, BEAM.height + 2 * clr]).translate(
            [FACE_IN_X - b.recess, -BEAM.depth / 2 - clr, BEAM_BOTTOM - clr]
        )
    )
    cuts += [
        teardrop_x(TOL.bolt_hole_d(b.beam_bolt_m), b.face_t + 2).translate(
            [(FACE_IN_X + FACE_OUT_X) / 2, 0, z]
        )
        for z in BEAM_BOLT_Z
    ]
    # belt clamp caps: M3 clearance hole up from the flat underside, and a hex shaft from the
    # top down to a nut pressed in at CLAMP.nut_z (the floor below it takes the pull)
    cuts += [
        (
            cylinder(d=TOL.bolt_hole_d(3), h=CLAMP.nut_z + 1, fn=FN_HOLE).translate([0, 0, -EPS])
            | cylinder(d=TOL.nut_trap_ac(3), h=FACE_TOP + 1 - CLAMP.nut_z, fn=6).translate(
                [0, 0, CLAMP.nut_z]
            )
        )
        .translate([sx * CLAMP.screw_dx, CLAMP.length / 2, 0])
        .align(clamp)
        for clamp in BELT_CLAMPS
        for sx in (-1, 1)
    ]
    # Y endstop trigger: M3 along -y through the boss, captive nut from the top
    boss_mid_y = -b.len_y / 2 + b.trig_boss[1] / 2
    cuts.append(
        teardrop_y(TOL.bolt_hole_d(3), b.trig_boss[1] + 2).translate(
            [b.trig_x, boss_mid_y, b.trig_z]
        )
    )
    cuts.append(
        nut_slot(3, FACE_TOP + 1 - b.trig_z, "y", "+z", tol=TOL).translate(
            [b.trig_x, boss_mid_y, b.trig_z]
        )
    )
    return cuts


def gantry_end_bracket_local(side: Side = Side.LEFT) -> Solid:
    """The bracket in the left bracket-local frame, with the features of ``side`` (the right
    one carries the loom anchor holes); the assembly mirrors the whole right end.

    Handles for the hardware and parts that meet it: ``block_bolts_front`` and
    ``block_bolts_rear`` (4 each), ``beam_bolts`` (2), ``belt_clamps`` (front, rear, lists),
    ``trigger_screw`` and, on the right bracket, ``loom_anchor`` (2); read them with
    ``geometry.get_handle(s)``.
    """
    handles: dict[str, Matrix | list[Matrix]] = {
        "block_bolts_front": BLOCK_BOLTS_FRONT,
        "block_bolts_rear": BLOCK_BOLTS_REAR,
        "beam_bolts": BEAM_BOLTS,
        "belt_clamps": BELT_CLAMPS,
        "trigger_screw": TRIGGER_SCREW,
    }
    cuts = _cutouts()
    if side is Side.RIGHT:
        handles["loom_anchor"] = LOOM_ANCHOR
        cuts += _loom_cutouts()
    return set_handles(_body(side) - cuts, **handles)


def gantry_end_bracket(side: Side = Side.LEFT) -> Solid:
    """The bracket for one gantry end, in print orientation (the right one is mirrored)."""
    bracket = gantry_end_bracket_local(side)
    return bracket.mirror([1, 0, 0]) if side is Side.RIGHT else bracket


# --- FEM definition (left bracket, bracket-local frame = print frame) ----------------
_BOLT_RINGS = [
    Cylinder(
        center=(bolt[0][3], bolt[1][3], bolt[2][3]),
        axis=(0, 0, 1),
        radius=metric(5).head_d / 2,
        inner_radius=TOL.bolt_hole_d(5) / 2,
        half_length=0.3,
        facing=(0, 0, 1),
    )
    for bolt in (*BLOCK_BOLTS_FRONT, *BLOCK_BOLTS_REAR)
]
_SEAT_X = FACE_IN_X - BRACKET.recess  #: the beam end's seat in the face plate
#: The X idler tower's frame in the bracket-local frame (outer face, belt line)
TOWER_PLACEMENT = Placement(0, (X_IDLER.tower_s0, X_IDLER.belt_pos, 0.0))
#: The face plate's pocket floor: the beam end pushes back here
BEAM_SEAT_FACES = Box(
    lo=(_SEAT_X - 0.3, -BEAM.depth / 2, BEAM_BOTTOM),
    hi=(_SEAT_X + 0.3, BEAM.depth / 2, BEAM_BOTTOM + BEAM.height),
    facing=(1, 0, 0),
)
#: The face plate behind the pocket floor (displacement of this tilts the beam)
BEAM_SEAT = Box(
    lo=(FACE_OUT_X, -BEAM.depth / 2, BEAM_BOTTOM),
    hi=(_SEAT_X + 0.3, BEAM.depth / 2, BEAM_BOTTOM + BEAM.height),
)


def _clamp_footprint(clamp: Matrix) -> Box:
    """A belt clamp's footprint on the bracket's flat underside."""
    x, y = clamp[0][3], clamp[1][3]
    return Box(
        lo=(x - CLAMP.w / 2, y, -0.3),
        hi=(x + CLAMP.w / 2, y + CLAMP.length, 0.3),
        facing=(0, 0, -1),
    )


#: Where the X motor mount's foot rests on the base (right bracket): the motor's pull enters here
MOTOR_FOOTPRINT = Box(
    lo=(max(BRACKET.x_out, FOOT_X[0]), X_DRIVE.motor_foot_y[0], BRACKET.base_t - 0.3),
    hi=(min(BRACKET.x_in, FOOT_X[1]), X_DRIVE.motor_foot_y[1], BRACKET.base_t + 0.3),
    facing=(0, 0, 1),
)


def _centre(box: Box) -> Vec3:
    """Middle of a flat footprint."""
    return (
        (box.lo[0] + box.hi[0]) / 2,
        (box.lo[1] + box.hi[1]) / 2,
        (box.lo[2] + box.hi[2]) / 2,
    )


def _x_belt_loads(side: Side, run_n: float, jam: bool) -> list[Load]:
    """Where the X belt's pull enters the bracket: the idler tower's screw-head seat (left; the
    tower is part of the bracket, so the pull acts at the axle's height) or the motor mount
    (right), as forces on the base top. The motor mount's couples are carried by the clamped joint
    (bolt preload), not by the contact, so they are not applied: a linear distribution would pull
    up on a surface that can only be pushed. The beam holds the face plate's seat (a support)."""
    if side is Side.LEFT:
        # the tension screw is in line with the belt: its head pushes the tower with the whole pull
        loads: list[Load] = [head_load(X_IDLER, TOWER_PLACEMENT, 2 * run_n)]
    else:
        footprint = MOTOR_FOOTPRINT
        loads = motor_loads(
            footprint,
            X_BELT_LOADS,
            jam,
            MOTOR_PULLEY,
            _centre(footprint),
            (1, 0, 0),
            (0, -1, 0),
            couples=False,
        )
    return loads


def _belt_case(side: Side, name: str, x_run_n: float, y_run_n: float, jam: bool) -> LoadCase:
    """The X belt's reaction through the bracket plus the Y belt's two ends."""
    front, rear = BELT_CLAMPS
    return LoadCase(
        name=name,
        description=(
            f"X belt (2 runs of {x_run_n:g} N): the "
            + (
                "tension screw's head pushes the tower inboard at the axle's height"
                if side is Side.LEFT
                else "motor mount pulls the base inboard (a force on the base; its couples are "
                "carried by the bolt clamp)"
            )
            + f"; the stiff beam holds the face plate's seat. Y belt ({y_run_n:g} N): front end "
            "pulls forward, rear end pulls back"
        ),
        loads=(
            *_x_belt_loads(side, x_run_n, jam),
            Force(_clamp_footprint(front), (0, -y_run_n, 0)),
            Force(_clamp_footprint(rear), (0, y_run_n, 0)),
        ),
        source="loads.X_BELT_LOADS, loads.Y_BELT_LOADS, loads.MOTOR_LOADS",
        sustained=not jam,
    )


def _spec(side: Side) -> FemSpec:
    """FEM spec of one bracket."""
    # how far the idler tower (left) or the motor mount's foot (right) moves relative to the (held)
    # beam seat slackens the X belt
    if side is Side.LEFT:
        mount_limits = tower_limits(X_IDLER, TOWER_PLACEMENT)
    else:
        mount_limits = (
            DisplacementLimit("mount_foot_x", MOTOR_FOOTPRINT, 0.1, (1, 0, 0)),
            DisplacementLimit("mount_foot_y", MOTOR_FOOTPRINT, 0.1, (0, 1, 0)),
            DisplacementLimit("mount_foot_z", MOTOR_FOOTPRINT, 0.1, (0, 0, 1)),
        )
    return FemSpec(
        load_cases=(
            _belt_case(side, "belt_preload", X_BELT_LOADS.preload_n, Y_BELT_LOADS.preload_n, False),
            _belt_case(side, "belt_peak", X_BELT_LOADS.peak_n, Y_BELT_LOADS.peak_n, True),
        ),
        supports=(
            *(
                Support(
                    f"block_bolt_{i + 1}", ring, "M5 bolt into an SCS block: washer ring, fixed"
                )
                for i, ring in enumerate(_BOLT_RINGS)
            ),
            Support(
                "beam_seat",
                BEAM_SEAT_FACES,
                "Beam end on the pocket floor: the stiff beam holds the seat along x",
                constrain=(True, False, False),
            ),
        ),
        displacement_limits=(
            *mount_limits,
            DisplacementLimit("beam_seat_y", BEAM_SEAT, 0.1, (0, 1, 0)),
            DisplacementLimit("beam_seat_z", BEAM_SEAT, 0.1, (0, 0, 1)),
        ),
    )


PART_LEFT = PrintedPart(
    name="gantry_end_bracket_left",
    description="Gantry end bracket, left: SCS blocks, beam face plate, Y belt clamps",
    build=lambda: gantry_end_bracket(Side.LEFT),
    analysis=gantry_end_bracket_local,
    frame="installed",
    build_direction=(0, 0, 1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=_spec(Side.LEFT),
)
PART_RIGHT = PrintedPart(
    name="gantry_end_bracket_right",
    description="Gantry end bracket, right (shown in the left frame): carries the X motor mount",
    build=lambda: gantry_end_bracket(Side.RIGHT),
    analysis=lambda: gantry_end_bracket_local(Side.RIGHT),
    frame="installed",
    build_direction=(0, 0, 1),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=_spec(Side.RIGHT),
)
