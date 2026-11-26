"""Baseboard with its fixings (T3.7, D31): drilled board, runners, SK10 bolts, shafts, bed
panel on its posts, steel sheet, the ZRIB mount and the PSU mount. Everything that does not
move.

Machine frame (``params``): the board's top face is z = 0. Not printable.
"""

import math
from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE
from cadder.hardware import (
    SK10_SPEC,
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
    board_thickness = FRAME.board_size[2]
    if hole.side == SIDE_UNDER:
        assert hole.depth is not None
        return cylinder(d=hole.dia, h=hole.depth + 1, fn=FN_HOLE).translate([hole.x, hole.y, -board_thickness - 1])
    cutter = cylinder(d=hole.dia, h=board_thickness + 2, fn=FN_HOLE).translate([hole.x, hole.y, -board_thickness - 1])
    if hole.countersink_dia:
        depth = (hole.countersink_dia - hole.dia) / 2
        cutter = cutter | cylinder(d1=hole.dia, d2=hole.countersink_dia, h=depth, fn=FN_HOLE).translate(
            [hole.x, hole.y, -depth]
        )
    return cutter


def baseboard() -> Solid:
    """The plywood with every hole of the drilling layout, and the right edge's underside eased
    45° for the PSU brackets' corner fillet (T3.31)."""
    board_x, board_y, board_thickness = FRAME.board_size
    board = cube([board_x, board_y, board_thickness]).translate([0, 0, -board_thickness])
    for hole in board_holes():
        board = board - _drill(hole)
    chamfer = PSU_MOUNT.corner_radius * math.sqrt(2)
    ease = cube([chamfer, board_y + 2, chamfer]).translate([-chamfer / 2, -1, -chamfer / 2]).rotate([0, 45, 0])
    board = board - ease.translate([board_x, 0, -board_thickness])
    return board.color("BurlyWood", 0.5)


def runners() -> list[Solid]:
    """The three runners with their M5 countersunk screws and T-nuts."""
    board_thickness = FRAME.board_size[2]
    items: list[Solid] = []
    for runner_y in BASEBOARD.runner_y:
        items.append(
            vslot_x(BASEBOARD.runner_length, _RUNNER_SIZE).translate(
                [
                    BASEBOARD.runner_x[0],
                    runner_y - BASEBOARD.runner_width / 2,
                    -board_thickness - BASEBOARD.runner_height,
                ]
            )
        )
        for x in BASEBOARD.runner_screw_x:
            items.append(
                countersunk_screw(5, BASEBOARD.runner_screw_length, BASEBOARD.runner_screw_head_dia).translate(
                    [x, runner_y, 0]
                )
            )
            items.append(
                t_nut(5, BASEBOARD.tnut_thickness).translate(
                    [x, runner_y, -board_thickness - BASEBOARD.slot_lip_thickness]
                )
            )
    return items


def shafts_and_supports() -> list[Solid]:
    """Y shafts, SK10 supports and the SK10 bolts with their nuts and washers underneath."""
    board_thickness = FRAME.board_size[2]
    screw_m5 = metric(5)
    items: list[Solid] = []
    for x in Y_AXIS.shaft_x:
        items.append(y_shaft().translate([x, Y_AXIS.shaft_y0, Y_AXIS.shaft_z]))
        for y in Y_AXIS.sk10_y:
            items.append(sk10().translate([x, y, 0]))
            for dx in BASEBOARD.sk10_hole_x:
                hole_x = x + dx
                items.append(
                    shcs(5, BASEBOARD.sk10_bolt_length).translate(
                        [hole_x, y, SK10_SPEC.base_thickness + screw_m5.washer_thickness]
                    )
                )
                items.append(washer(5).translate([hole_x, y, SK10_SPEC.base_thickness]))
                items.append(washer(5).translate([hole_x, y, -board_thickness - screw_m5.washer_thickness]))
                items.append(
                    hex_nut(5).translate(
                        [hole_x, y, -board_thickness - screw_m5.washer_thickness - screw_m5.nut_height]
                    )
                )
    return items


def bed() -> list[Solid]:
    """Bed panel, steel sheet and the four adjustment posts (studs, springs, nuts)."""
    screw_m5 = metric(5)
    bed_x, bed_y = FRAME.bed_size
    x0, y0 = FRAME.bed_origin
    gap = FRAME.bed_adjust_gap
    panel = cube([bed_x, bed_y, FRAME.bed_panel_thickness]).translate([x0, y0, gap])
    for x, y in BASEBOARD.post_xy:
        panel = panel - cylinder(d=5.4, h=FRAME.bed_panel_thickness + 2, fn=FN_HOLE).translate([x, y, gap - 1])
    steel_x, steel_y = FRAME.steel_size
    items: list[Solid] = [
        panel.color("Tan", 0.8),
        cube([steel_x, steel_y, FRAME.bed_steel_thickness])
        .translate([x0 + FRAME.steel_margin, y0 + FRAME.steel_margin, gap + FRAME.bed_panel_thickness])
        .color("SlateGray"),
    ]
    top = gap + FRAME.bed_panel_thickness
    for x, y in BASEBOARD.post_xy:
        items += [
            shcs(5, BASEBOARD.post_bolt_length).rotate([180, 0, 0]).translate([x, y, BASEBOARD.post_stud_z]),
            washer(5).translate([x, y, BASEBOARD.post_stud_z]),
            spring(BASEBOARD.spring_outer_dia, BASEBOARD.spring_id, gap).translate([x, y, 0]),
            washer(5).translate([x, y, top]),
            hex_nut(5).translate([x, y, top + screw_m5.washer_thickness]),
        ]
    return items


def zrib() -> list[Solid]:
    """The ZRIB mount in its place under the baseboard."""
    center_x, center_y = BASEBOARD.zrib_center
    return [item.translate([center_x, center_y, -FRAME.board_size[2]]) for item in zrib_mount_assembly()]


def fixed_assembly() -> list[Solid]:
    """Everything that stays put: board, runners, shafts and supports, bed, ZRIB, PSU."""
    return [baseboard(), *runners(), *shafts_and_supports(), *bed(), *zrib(), *psu_mount_assembly()]
