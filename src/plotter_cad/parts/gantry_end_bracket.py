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

Print: PETG (preferred, less creep) or PLA; 0.2 mm layers; 4 perimeters; 40 % infill;
base face down; no supports (horizontal holes are teardrops; the underside is flat).
"""

from enum import Enum
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import (
    EPS,
    FN_HOLE,
    Matrix,
    handle,
    set_handles,
    teardrop_x,
    teardrop_y,
)
from plotter_cad.hardware import SCS10UU, VSLOT
from plotter_cad.nut_slot import nut_slot
from plotter_cad.params import BEAM, BRACKET, CLAMP, LOOM, TOL, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid


class Side(Enum):
    """Which end of the gantry a part belongs to."""

    LEFT = "left"
    RIGHT = "right"


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


def _body() -> Solid:
    """Bracket solid before the holes and cutouts."""
    b = BRACKET
    base = cube([b.x_in - b.x_out, b.len_y, b.base_t]).translate([b.x_out, -b.len_y / 2, 0])
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
            nut_slot(3, x - BRACKET.x_out + 1, "z", "-x").translate([x, y, top - nut_t / 2])
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
        nut_slot(3, FACE_TOP + 1 - b.trig_z, "y", "+z").translate([b.trig_x, boss_mid_y, b.trig_z])
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
    return set_handles(_body() - cuts, **handles)


def gantry_end_bracket(side: Side = Side.LEFT) -> Solid:
    """The bracket for one gantry end, in print orientation (the right one is mirrored)."""
    bracket = gantry_end_bracket_local(side)
    return bracket.mirror([1, 0, 0]) if side is Side.RIGHT else bracket
