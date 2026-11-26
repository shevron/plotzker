"""Baseboard with its fixings (T3.7, D31): drilled board, runners, SK10 bolts, shafts, bed
panel on its posts, steel sheet, the ZRIB mount and the PSU mount. Everything that does not
move.

Machine frame (``params``): the board's top face is z = 0. Not printable.
"""

import math
from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE
from cadder.hardware import (
    SK10,
    countersunk_screw,
    hex_nut,
    metric,
    shcs,
    sk10,
    spring,
    t_nut,
    vslot_x,
    washer,
)
from pythonscad import cube, cylinder

from plotzker.assemblies.psu_mount import psu_mount_assembly
from plotzker.assemblies.zrib_mount import zrib_mount_assembly
from plotzker.hardware import y_shaft
from plotzker.layout import SIDE_UNDER, Hole, board_holes
from plotzker.params import BASEBOARD, FRAME, PSU_MOUNT, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid

_RUNNER_SIZE = (1, 2)  #: 2040 on edge: 20 wide along y, 40 tall


def _drill(hole: Hole) -> Solid:
    """The material a hole removes from the baseboard."""
    t = FRAME.board_size[2]
    if hole.side == SIDE_UNDER:
        assert hole.depth is not None
        return cylinder(d=hole.d, h=hole.depth + 1, fn=FN_HOLE).translate([hole.x, hole.y, -t - 1])
    cutter = cylinder(d=hole.d, h=t + 2, fn=FN_HOLE).translate([hole.x, hole.y, -t - 1])
    if hole.countersink_d:
        depth = (hole.countersink_d - hole.d) / 2
        cutter = cutter | cylinder(d1=hole.d, d2=hole.countersink_d, h=depth, fn=FN_HOLE).translate(
            [hole.x, hole.y, -depth]
        )
    return cutter


def baseboard() -> Solid:
    """The plywood with every hole of the drilling layout, and the right edge's underside eased
    45° for the PSU brackets' corner fillet (T3.31)."""
    bx, by, t = FRAME.board_size
    board = cube([bx, by, t]).translate([0, 0, -t])
    for hole in board_holes():
        board = board - _drill(hole)
    a = PSU_MOUNT.corner_r * math.sqrt(2)
    ease = cube([a, by + 2, a]).translate([-a / 2, -1, -a / 2]).rotate([0, 45, 0])
    board = board - ease.translate([bx, 0, -t])
    return board.color("BurlyWood", 0.5)


def runners() -> list[Solid]:
    """The three runners with their M5 countersunk screws and T-nuts."""
    bb = BASEBOARD
    t = FRAME.board_size[2]
    items: list[Solid] = []
    for ry in bb.runner_y:
        items.append(
            vslot_x(bb.runner_len, _RUNNER_SIZE).translate([bb.runner_x[0], ry - bb.runner_w / 2, -t - bb.runner_h])
        )
        for x in bb.runner_screw_x:
            items.append(countersunk_screw(5, bb.runner_screw_len, bb.runner_screw_head_d).translate([x, ry, 0]))
            items.append(t_nut(5, bb.tnut_t).translate([x, ry, -t - bb.slot_lip_t]))
    return items


def shafts_and_supports() -> list[Solid]:
    """Y shafts, SK10 supports and the SK10 bolts with their nuts and washers underneath."""
    bb = BASEBOARD
    t = FRAME.board_size[2]
    m5 = metric(5)
    items: list[Solid] = []
    for x in Y_AXIS.shaft_x:
        items.append(y_shaft().translate([x, Y_AXIS.shaft_y0, Y_AXIS.shaft_z]))
        for y in Y_AXIS.sk10_y:
            items.append(sk10().translate([x, y, 0]))
            for dx in bb.sk10_hole_x:
                hx = x + dx
                items.append(shcs(5, bb.sk10_bolt_len).translate([hx, y, SK10.base_t + m5.washer_t]))
                items.append(washer(5).translate([hx, y, SK10.base_t]))
                items.append(washer(5).translate([hx, y, -t - m5.washer_t]))
                items.append(hex_nut(5).translate([hx, y, -t - m5.washer_t - m5.nut_h]))
    return items


def bed() -> list[Solid]:
    """Bed panel, steel sheet and the four adjustment posts (studs, springs, nuts)."""
    bb = BASEBOARD
    m5 = metric(5)
    bx, by = FRAME.bed_size
    x0, y0 = FRAME.bed_origin
    gap = FRAME.bed_adjust_gap
    panel = cube([bx, by, FRAME.bed_panel_t]).translate([x0, y0, gap])
    for x, y in bb.post_xy:
        panel = panel - cylinder(d=5.4, h=FRAME.bed_panel_t + 2, fn=FN_HOLE).translate([x, y, gap - 1])
    sx, sy = FRAME.steel_size
    items: list[Solid] = [
        panel.color("Tan", 0.8),
        cube([sx, sy, FRAME.bed_steel_t])
        .translate([x0 + FRAME.steel_margin, y0 + FRAME.steel_margin, gap + FRAME.bed_panel_t])
        .color("SlateGray"),
    ]
    top = gap + FRAME.bed_panel_t
    for x, y in bb.post_xy:
        items += [
            shcs(5, bb.post_bolt_len).rotate([180, 0, 0]).translate([x, y, bb.post_stud_z]),
            washer(5).translate([x, y, bb.post_stud_z]),
            spring(bb.spring_od, bb.spring_id, gap).translate([x, y, 0]),
            washer(5).translate([x, y, top]),
            hex_nut(5).translate([x, y, top + m5.washer_t]),
        ]
    return items


def zrib() -> list[Solid]:
    """The ZRIB mount in its place under the baseboard."""
    cx, cy = BASEBOARD.zrib_center
    return [item.translate([cx, cy, -FRAME.board_size[2]]) for item in zrib_mount_assembly()]


def fixed_assembly() -> list[Solid]:
    """Everything that stays put: board, runners, shafts and supports, bed, ZRIB, PSU."""
    return [baseboard(), *runners(), *shafts_and_supports(), *bed(), *zrib(), *psu_mount_assembly()]
