"""Machine layout skeleton: baseboard, Y axis, bed, media envelope, gantry and carriage.

Quick layout check of the height stack-up, travel and clearances, with plain boxes for the
baseboard and the bed. The full machine (drilled board, runners, bed posts, ZRIB, pen holder)
is ``machine.py`` (T3.7). Not printable.
"""

from typing import TYPE_CHECKING

from cadder.hardware import sk10
from pythonscad import cube, translate

from plotzker.assemblies.carriage import carriage_assembly
from plotzker.assemblies.gantry import gantry_assembly
from plotzker.assemblies.y_drive import y_drive_assembly
from plotzker.hardware import y_shaft
from plotzker.params import CARRIAGE, FRAME, REQ, TOOL_PLATE, Y_AXIS

if TYPE_CHECKING:
    from pythonscad import Solid


def gantry_y_at(position: float) -> float:
    """Gantry center along Y; ``position`` 0 = front end of travel, 1 = back end."""
    front, back = Y_AXIS.gantry_y_range
    return front + position * (back - front)


def carriage_x_at(position: float) -> float:
    """Carriage center along X; ``position`` 0 = left end of travel, 1 = right end."""
    left, right = CARRIAGE.center_x_range
    return left + position * (right - left)


def moving_parts(gantry_position: float = 0.5, carriage_position: float = 0.5) -> list[Solid]:
    """Gantry, Y drive and X carriage at the given travel fractions (0..1)."""
    gantry_y = gantry_y_at(gantry_position)
    return [
        *gantry_assembly(gantry_y),
        *y_drive_assembly(gantry_y),
        translate(carriage_assembly(), [carriage_x_at(carriage_position), gantry_y, 0]),
    ]


def skeleton(gantry_position: float = 0.5, carriage_position: float = 0.5) -> list[Solid]:
    """Frame, Y axis, gantry and carriage at the given travel fractions (0..1)."""
    gantry_y = gantry_y_at(gantry_position)
    carriage_x = carriage_x_at(carriage_position)
    board_x, board_y, board_thickness = FRAME.board_size
    bed_x, bed_y = FRAME.bed_size
    a3_x, a3_y = REQ.media_a3

    items = [cube(list(FRAME.board_size)).translate([0, 0, -board_thickness]).color("BurlyWood", 0.5)]
    for x in Y_AXIS.shaft_x:
        items.append(y_shaft().translate([x, Y_AXIS.shaft_y0, Y_AXIS.shaft_z]))
        items += [sk10().translate([x, y, 0]) for y in Y_AXIS.sk10_y]
    # bed panel, steel sheet, thickest-media envelope (centered on the board)
    bed_origin = [*FRAME.bed_origin, 0]
    items.append(
        cube([bed_x, bed_y, FRAME.bed_panel_thickness])
        .translate([0, 0, FRAME.bed_adjust_gap])
        .translate(bed_origin)
        .color("Tan", 0.8)
    )
    items.append(
        cube([bed_x, bed_y, FRAME.bed_steel_thickness])
        .translate([0, 0, FRAME.bed_adjust_gap + FRAME.bed_panel_thickness])
        .translate(bed_origin)
        .color("SlateGray")
    )
    items.append(
        cube([a3_x, a3_y, REQ.media_max_thickness])
        .translate([(board_x - a3_x) / 2, (board_y - a3_y) / 2, FRAME.bed_top_z])
        .color("Orange", 0.25)
    )
    items += moving_parts(gantry_position, carriage_position)
    # tool-plate area marked in red
    items.append(
        cube([TOOL_PLATE.width, 1, TOOL_PLATE.height])
        .translate(
            [
                carriage_x - TOOL_PLATE.width / 2,
                gantry_y + CARRIAGE.plate_front_y - 1,
                TOOL_PLATE.bottom_z,
            ]
        )
        .color("Crimson", 0.5)
    )
    return items


def clearance_report() -> str:
    """One-line report of the gap between carriage and media."""
    gap = CARRIAGE.bottom_z - FRAME.media_top_z
    return f"Carriage bottom {CARRIAGE.bottom_z:g} vs media top {FRAME.media_top_z:g} → gap {gap:g}"
