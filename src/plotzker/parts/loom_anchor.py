"""Loom anchor (STATUS.md T3.8, D32). Print ×1, for the right gantry bracket.

Purpose: holds the gantry loom where it leaves the gantry: a block on the right bracket's
base, outboard of the X motor mount. The loom lies in an open groove along x and leaves
outboard (toward +x in the machine), then drops to the baseboard. A zip tie around the loom
goes up one slot, over the loom and back down the other, under the block through a channel.

Frame: left bracket-local frame (the assembly mirrors the right end): x inboard, y back,
z up with 0 at the SCS top-face plane; the block sits on the base top (z = base thickness).
:func:`loom_anchor` is the same part in print orientation (bottom on z = 0).

Hardware: 2 × M3×16 ISO 4762 into M3 nuts pressed into the bracket (see
``gantry_end_bracket.py``); 1 zip tie (≤ 3.6 mm wide).
Print: PETG; 0.2 mm; 4 perimeters; 40 % infill; bottom down; no supports (the tie channel
is a 2 mm bridge).
"""

import itertools
from typing import TYPE_CHECKING

from cadder.geometry import EPS, FN_HOLE
from pythonscad import cube, cylinder, hull, sphere

from plotzker.params import BRACKET, LOOM, TOL

if TYPE_CHECKING:
    from pythonscad import Solid

TIE_SLOT_DY = LOOM.d / 2 + 3  #: tie slots, either side of the loom axis
CHANNEL_H = 2.0  #: tie channel height under the block


def loom_anchor_installed() -> Solid:
    """The anchor on the right bracket, in the bracket-local frame."""
    x0, x1 = LOOM.anchor_x
    y0, y1 = LOOM.anchor_y
    z0, z1 = BRACKET.base_t, BRACKET.base_t + LOOM.anchor_h
    cy, gz = LOOM.anchor_cy, LOOM.groove_z
    block = cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])
    groove_d = TOL.slide_d(LOOM.d)
    groove = cylinder(d=groove_d, h=x1 - x0 + 2, fn=FN_HOLE).rotate([0, 90, 0]).translate(
        [x0 - 1, cy, gz]
    ) | cube([x1 - x0 + 2, groove_d, z1 - gz + 1]).translate([x0 - 1, cy - groove_d / 2, gz])
    xc = (x0 + x1) / 2
    tie_len = LOOM.tie_w + 1
    tie_w = LOOM.tie_t + 0.5
    slots = [
        cube([tie_len, tie_w, LOOM.anchor_h + 2]).translate(
            [xc - tie_len / 2, cy + s * TIE_SLOT_DY - tie_w / 2, z0 - 1]
        )
        for s in (-1, 1)
    ]
    channel = cube([tie_len, 2 * TIE_SLOT_DY + tie_w, CHANNEL_H + EPS]).translate(
        [xc - tie_len / 2, cy - TIE_SLOT_DY - tie_w / 2, z0 - EPS]
    )
    holes = [
        cylinder(d=TOL.bolt_hole_d(3), h=LOOM.anchor_h + 2, fn=FN_HOLE).translate(
            [LOOM.anchor_screw_x, y, z0 - 1]
        )
        for y in LOOM.anchor_screw_y
    ]
    # the loom starts to bend down inside the block: carve its path
    ball = sphere(d=groove_d, fn=16)
    arc = [ball.translate([x, cy, z]) for x, z in LOOM.drop_arc()]
    relief = [hull(a, b) for a, b in itertools.pairwise(arc)]
    return block - groove - relief - slots - channel - holes


def loom_anchor() -> Solid:
    """The anchor in print orientation."""
    return loom_anchor_installed().translate([0, 0, -BRACKET.base_t])
