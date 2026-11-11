"""Machine layout skeleton: baseboard, Y axis, bed, media envelope, gantry and carriage.

Checks the height stack-up, travel and clearances. Real parts where they exist
(gantry T3.2/T3.4, carriage T3.3); later tasks (T3.5–T3.7) add the Y drive, tool head
and baseboard layout. Not printable. Superseded by the full assembly in T3.7.
"""

from pythonscad import cube, translate

from plotter_cad.assemblies.carriage import carriage_assembly
from plotter_cad.assemblies.gantry import gantry_assembly
from plotter_cad.hardware import GT2, PULLEY, SK10, Y_SHAFT, sk10, y_shaft
from plotter_cad.params import BEAM, CARRIAGE, FRAME, REQ, TOOL_PLATE, Y_AXIS


def gantry_y_at(position: float) -> float:
    """Gantry center along Y; ``position`` 0 = front end of travel, 1 = back end."""
    front = Y_AXIS.shaft_y0 + SK10.length + Y_AXIS.end_margin + Y_AXIS.gantry_len_y / 2
    return front + position * Y_AXIS.travel_avail


def carriage_x_at(position: float) -> float:
    """Carriage center along X; ``position`` 0 = left end of travel, 1 = right end."""
    beam_x0 = (FRAME.board_size[0] - BEAM.length) / 2
    return beam_x0 + CARRIAGE.end_keepout + CARRIAGE.w / 2 + position * CARRIAGE.travel_avail


def skeleton(gantry_pos: float = 0.5, carriage_pos: float = 0.5) -> list:
    gantry_y = gantry_y_at(gantry_pos)
    carriage_x = carriage_x_at(carriage_pos)
    board_x, board_y, board_t = FRAME.board_size
    bed_x, bed_y = FRAME.bed_size
    a3_x, a3_y = REQ.media_a3

    items = [cube(list(FRAME.board_size)).translate([0, 0, -board_t]).color("BurlyWood", 0.5)]
    # Y axis: shafts and SK10s
    for x in Y_AXIS.shaft_x:
        items.append(y_shaft().translate([x, Y_AXIS.shaft_y0, Y_AXIS.shaft_z]))
        items += [sk10().translate([x, y, 0]) for y in Y_AXIS.sk10_y]
    # bed panel, steel sheet, thickest-media envelope (centered on the board)
    bed_origin = [(board_x - bed_x) / 2, (board_y - bed_y) / 2, 0]
    items.append(
        cube([bed_x, bed_y, FRAME.bed_panel_t])
        .translate([0, 0, FRAME.bed_adjust_gap])
        .translate(bed_origin)
        .color("Tan", 0.8)
    )
    items.append(
        cube([bed_x, bed_y, FRAME.bed_steel_t])
        .translate([0, 0, FRAME.bed_adjust_gap + FRAME.bed_panel_t])
        .translate(bed_origin)
        .color("SlateGray")
    )
    items.append(
        cube([a3_x, a3_y, REQ.media_max_t])
        .translate([(board_x - a3_x) / 2, (board_y - a3_y) / 2, FRAME.bed_top_z])
        .color("Orange", 0.25)
    )
    # gantry (T3.2, T3.4)
    items += gantry_assembly(gantry_y)
    # Y belt return runs (lower run, full shaft length) — motors/idlers come in T3.5
    for i, x in enumerate(Y_AXIS.shaft_x):
        outboard = 1 if i == 0 else -1
        items.append(
            cube([GT2.width, Y_SHAFT.length, GT2.thickness])
            .translate(
                [
                    x + outboard * Y_AXIS.belt_x - GT2.width / 2,
                    Y_AXIS.shaft_y0,
                    Y_AXIS.pulley_axis_z - PULLEY.pd / 2 - GT2.thickness + GT2.pitch_line_from_back,
                ]
            )
            .color("#111")
        )
    # X carriage (T3.3); tool-plate area marked in red
    items.append(translate(carriage_assembly(), [carriage_x, gantry_y, 0]))
    items.append(
        cube([TOOL_PLATE.w, 1, TOOL_PLATE.h])
        .translate(
            [
                carriage_x - TOOL_PLATE.w / 2,
                gantry_y + CARRIAGE.plate_front_y - 1,
                TOOL_PLATE.bottom_z,
            ]
        )
        .color("Crimson", 0.5)
    )
    return items


def clearance_report() -> str:
    gap = CARRIAGE.bottom_z - FRAME.media_top_z
    return f"Carriage bottom {CARRIAGE.bottom_z:g} vs media top {FRAME.media_top_z:g} → gap {gap:g}"
