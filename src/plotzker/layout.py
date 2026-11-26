"""1:1 drilling layout of the baseboard (T3.7, D31): hole list, SVG drawing and hole table.

The holes are derived from ``params`` (the same numbers the assembly model uses), so the
drawing cannot drift from the CAD. Coordinates: machine frame, origin at the front-left
corner of the baseboard's top face, seen from above; x across, y front to back.

The Y motor and idler mounts are **not pre-drilled** (D26): they are placed around the
aligned SK10s and screwed down through their own holes. They appear as outlines only.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cadder.drawing import SvgDrawing, markdown_table, stroke
from cadder.hardware import SK10_SPEC

from plotzker.params import (
    BASEBOARD,
    FRAME,
    LOOM,
    PSU_MOUNT,
    REQ,
    TOL,
    WOOD_SCREW,
    Y_AXIS,
)

if TYPE_CHECKING:
    from pythonscad import Solid

SIDE_TOP = "top"
SIDE_UNDER = "underside"


@dataclass(frozen=True)
class Hole:
    """One hole in the baseboard."""

    group: str
    x: float
    y: float
    dia: float  #: drill diameter
    side: str = SIDE_TOP  #: face the hole is drilled from
    countersink_dia: float | None = None  #: 90° countersink diameter at the face
    depth: float | None = None  #: blind depth (None = through)
    note: str = ""


def board_holes() -> list[Hole]:
    """Every hole of the baseboard, in the order of the drilling procedure."""
    m5_hole_dia = TOL.bolt_hole_dia(5)
    holes: list[Hole] = []
    for rail, shaft_x in enumerate(Y_AXIS.shaft_x):
        floating = rail == 1
        for y in Y_AXIS.sk10_y:
            for dx in BASEBOARD.sk10_hole_x:
                holes.append(
                    Hole(
                        f"SK10, {'right (oversized)' if floating else 'left (fixed)'} rail",
                        shaft_x + dx,
                        y,
                        BASEBOARD.sk10_float_hole_dia if floating else m5_hole_dia,
                        note="M5 bolt, nut + washer underneath",
                    )
                )
    for runner_y in BASEBOARD.runner_y:
        for x in BASEBOARD.runner_screw_x:
            holes.append(
                Hole(
                    "Runner screws",
                    x,
                    runner_y,
                    m5_hole_dia,
                    countersink_dia=BASEBOARD.runner_screw_head_dia + 2 * TOL.bolt,
                    note="M5 countersunk into a T-nut in the runner",
                )
            )
    for x, y in BASEBOARD.post_xy:
        holes.append(Hole("Bed posts", x, y, m5_hole_dia, note="M5 stud, head under the board"))
    holes.append(Hole("Loom hole", LOOM.hole_x, LOOM.hole_y, LOOM.hole_dia, note="Y loom to the controller; deburr"))
    for x, y in PSU_MOUNT.pilot_xy:
        holes.append(
            Hole(
                "PSU bracket screws",
                x,
                y,
                BASEBOARD.pilot_dia,
                side=SIDE_UNDER,
                depth=WOOD_SCREW.length - WOOD_SCREW.boss_thickness,
                note="pilot for a 4 × 25 wood screw, blind: do not break through the top",
            )
        )
    return holes


def _bbox(solid: Solid) -> tuple[float, float, float, float]:
    """x0, y0, x1, y1 of a solid's footprint."""
    points, _ = solid.mesh()
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def mount_zones() -> dict[str, tuple[float, float, float, float]]:
    """Footprints of the four Y mounts (x0, y0, x1, y1), which are not pre-drilled."""
    from plotzker.parts.y_idler_mount import y_idler_mount_installed
    from plotzker.parts.y_motor_mount import y_motor_mount_installed
    from plotzker.types import Side

    zones = {}
    for side, shaft_x, sign in (
        (Side.LEFT, Y_AXIS.shaft_x[0], 1),
        (Side.RIGHT, Y_AXIS.shaft_x[1], -1),
    ):
        for name, solid in (
            ("idler", y_idler_mount_installed(side)),
            ("motor", y_motor_mount_installed()),
        ):
            x0, y0, x1, y1 = _bbox(solid if side is Side.LEFT else solid.mirror([1, 0, 0]))
            xa, xb = sorted((shaft_x + sign * x0, shaft_x + sign * x1))
            zones[f"Y {name} mount, {side.value}"] = (xa, y0, xb, y1)
    return zones


def drilling_svg() -> str:
    """The layout as an SVG drawn at 1 : 1 (1 user unit = 1 mm, printed size in mm)."""
    board_x, board_y, _ = FRAME.board_size
    drawing = SvgDrawing(board_x, board_y)
    thin = stroke("#000", 0.4)
    dashed = stroke("#06c", 0.4, "6 3")
    dotted = stroke("#888", 0.3, "2 2")

    drawing.rect(0, 0, board_x, board_y, stroke("#000", 0.8, fill="#fff"))
    bed_x, bed_y = FRAME.bed_origin
    drawing.rect(bed_x, bed_y, bed_x + FRAME.bed_size[0], bed_y + FRAME.bed_size[1], dotted)
    drawing.text(bed_x + 4, bed_y + FRAME.bed_size[1] - 6, "bed panel (on the posts)", size=6)
    a3x, a3y = REQ.media_a3
    drawing.rect(
        (board_x - a3x) / 2, (board_y - a3y) / 2, (board_x + a3x) / 2, (board_y + a3y) / 2, dotted, "A3 sheet"
    )
    for runner_y in BASEBOARD.runner_y:
        drawing.rect(
            BASEBOARD.runner_x[0],
            runner_y - BASEBOARD.runner_width / 2,
            BASEBOARD.runner_x[1],
            runner_y + BASEBOARD.runner_width / 2,
            dashed,
        )
        drawing.text(
            BASEBOARD.runner_x[0] + 3,
            runner_y - BASEBOARD.runner_width / 2 - 3,
            "runner 2040 on edge (underside)",
            size=5,
        )
    for x in Y_AXIS.shaft_x:
        drawing.line(x, Y_AXIS.shaft_y0, x, Y_AXIS.shaft_y0 + 700, "#999", 0.4)
        for y in Y_AXIS.sk10_y:
            drawing.rect(
                x - SK10_SPEC.width / 2,
                y - SK10_SPEC.length / 2,
                x + SK10_SPEC.width / 2,
                y + SK10_SPEC.length / 2,
                thin,
            )
    for name, (x0, y0, x1, y1) in mount_zones().items():
        drawing.rect(x0, y0, x1, y1, 'fill="#fde9d0" fill-opacity="0.6" stroke="#c60" stroke-width="0.4"')
        drawing.text((x0 + x1) / 2, y1 + 4, f"{name}: not pre-drilled", anchor="middle", size=5)

    for y0 in LOOM.rail_starts:
        drawing.rect(
            LOOM.rail_x - LOOM.rail_thickness - LOOM.foot_width,
            y0,
            LOOM.rail_x,
            y0 + LOOM.rail_length,
            'fill="#dde8f5" stroke="#06c" stroke-width="0.4"',
        )
    drawing.text(
        LOOM.rail_x - 40,
        LOOM.rail_y0 - 8,
        "loom rails: not pre-drilled, wall 42 from the shaft",
        size=5,
    )
    for i, hole in enumerate(board_holes(), 1):
        color = "#c00" if hole.side == SIDE_TOP else "#06c"
        if hole.countersink_dia:
            drawing.circle(hole.x, hole.y, hole.countersink_dia / 2, stroke(color, 0.3))
        drawing.circle(hole.x, hole.y, hole.dia / 2, stroke(color, 0.5))
        drawing.crosshair(hole.x, hole.y, 6, color, 0.3)
        drawing.text(hole.x + 5, hole.y + 5, str(i), size=6)

    drawing.scale_bar(20, 20, 100)
    drawing.text(20, 22, "100 mm: print at 100 % and check this bar", size=6)
    drawing.text(
        8,
        board_y - 8,
        "Baseboard 700 × 900 × 18, top face, front-left corner = origin. "
        "Red: drill from the top. Blue: drill from the underside. Generated by "
        "`python -m plotzker layout`.",
        size=5,
    )
    return drawing.to_svg()


def hole_table() -> str:
    """Markdown table of the holes, numbered as in the drawing."""
    rows = []
    for i, hole in enumerate(board_holes(), 1):
        notes = hole.note
        if hole.countersink_dia:
            notes += f"; countersink Ø{hole.countersink_dia:g}"
        if hole.depth:
            notes += f"; {hole.depth:g} deep"
        rows.append((i, hole.group, f"{hole.x:g}", f"{hole.y:g}", f"{hole.dia:g}", hole.side, notes))
    return markdown_table(("#", "Group", "x", "y", "Ø", "Face", "Notes"), rows)


def write_layout(out_dir: Path) -> list[Path]:
    """Write ``baseboard-layout.svg`` and the hole table into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    svg = out_dir / "baseboard-layout.svg"
    svg.write_text(drilling_svg())
    table = out_dir / "baseboard-holes.md"
    table.write_text(
        "# Baseboard holes (generated)\n\n"
        "Generated by `python -m plotzker layout` from `params.py`; do not edit. "
        "Coordinates in mm from the front-left corner of the top face (x across, y front to "
        "back). Drawing: [`baseboard-layout.svg`](baseboard-layout.svg).\n\n" + hole_table() + "\n"
    )
    return [svg, table]
