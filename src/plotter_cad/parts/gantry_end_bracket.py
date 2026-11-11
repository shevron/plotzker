"""Y-gantry end bracket (README §8 T3.2). Print ×1 left + ×1 right (mirror image).

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
                       must be tapped M5 (or an M5 screw driven in to cut its own thread)
  4 × M3 heat-set inserts (Ø4.6 × 5.7) + 4 × M3×10 ISO 4762 — two Y belt clamps
  2 × y_belt_clamp (printed)
  1 × M3×16 ISO 4762 + 2 × M3 nuts — Y endstop trigger (adjust, then lock)

Print: PETG (preferred, less creep) or PLA; 0.2 mm layers; 4 perimeters; 40 % infill;
base face down; no supports (horizontal holes are teardrops; the belt channel on the
underside bridges 6.4 mm).
"""

from enum import Enum
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import EPS, FN_HOLE, teardrop_x, teardrop_y
from plotter_cad.hardware import M3_INSERT, SCS10UU, VSLOT, metric
from plotter_cad.params import BEAM, BRACKET, CLAMP, TOL, Y_AXIS

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
#: Belt clamp centers (y)
CLAMP_Y = (-BRACKET.len_y / 2 + CLAMP.length / 2, BRACKET.len_y / 2 - CLAMP.length / 2)


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


def _cutouts() -> list[Solid]:
    """Holes and pockets subtracted from the body."""
    b = BRACKET
    cuts = []
    # carriage notch: between the blocks the base stops at the face plate
    cuts.append(cube([b.x_in, 2 * b.notch_y, b.base_t + 2]).translate([FACE_IN_X, -b.notch_y, -1]))
    cuts += [
        cylinder(d=TOL.bolt_hole_d(5), h=b.base_t + 2, fn=FN_HOLE).translate(
            [
                hx * SCS10UU.hole_pitch_x / 2,
                block * Y_AXIS.scs_pitch / 2 + hy * SCS10UU.hole_pitch_y / 2,
                -1,
            ]
        )
        for block in (-1, 1)
        for hx in (-1, 1)
        for hy in (-1, 1)
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
    # Y belt channel along the underside (the belt back bears on its ceiling)
    cuts.append(
        cube([CLAMP.channel_w, b.len_y + 2, CLAMP.channel_d + EPS]).translate(
            [Y_AXIS.belt_x - CLAMP.channel_w / 2, -b.len_y / 2 - 1, -EPS]
        )
    )
    # M3 heat-set insert pockets for the two belt clamp caps (from below)
    cuts += [
        cylinder(d=M3_INSERT.hole_d, h=TOL.insert_pocket_depth, fn=FN_HOLE).translate(
            [Y_AXIS.belt_x + sx * CLAMP.screw_dx, cy, -EPS]
        )
        for cy in CLAMP_Y
        for sx in (-1, 1)
    ]
    # Y endstop trigger: M3 along -y through the boss, captive nut from the top
    boss_mid_y = -b.len_y / 2 + b.trig_boss[1] / 2
    cuts.append(
        teardrop_y(TOL.bolt_hole_d(3), b.trig_boss[1] + 2).translate(
            [b.trig_x, boss_mid_y, b.trig_z]
        )
    )
    nut_t = metric(3).nut_h + TOL.nut
    cuts.append(
        cube([TOL.nut_trap_af(3), nut_t, FACE_TOP]).translate(
            [
                b.trig_x - TOL.nut_trap_af(3) / 2,
                boss_mid_y - nut_t / 2,
                b.trig_z - TOL.nut_trap_ac(3) / 2,
            ]
        )
    )
    return cuts


def gantry_end_bracket(side: Side = Side.LEFT) -> Solid:
    """The bracket for one gantry end, in print orientation (the right one is mirrored)."""
    bracket = _body() - _cutouts()
    return bracket.mirror([1, 0, 0]) if side is Side.RIGHT else bracket
