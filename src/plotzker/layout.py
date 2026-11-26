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
    ZMOUNT,
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
    d: float  #: drill diameter
    side: str = SIDE_TOP  #: face the hole is drilled from
    countersink_d: float | None = None  #: 90° countersink diameter at the face
    depth: float | None = None  #: blind depth (None = through)
    note: str = ""


def board_holes() -> list[Hole]:
    """Every hole of the baseboard, in the order of the drilling procedure."""
    m5 = TOL.bolt_hole_d(5)
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
                        BASEBOARD.sk10_float_hole_d if floating else m5,
                        note="M5 bolt, nut + washer underneath",
                    )
                )
    for ry in BASEBOARD.runner_y:
        for x in BASEBOARD.runner_screw_x:
            holes.append(
                Hole(
                    "Runner screws",
                    x,
                    ry,
                    m5,
                    countersink_d=BASEBOARD.runner_screw_head_d + 2 * TOL.bolt,
                    note="M5 countersunk into a T-nut in the runner",
                )
            )
    for x, y in BASEBOARD.post_xy:
        holes.append(Hole("Bed posts", x, y, m5, note="M5 stud, head under the board"))
    holes.append(Hole("Loom hole", LOOM.hole_x, LOOM.hole_y, LOOM.hole_d, note="Y loom to the ZRIB; deburr"))
    for x, y in BASEBOARD.zrib_pilot_xy:
        holes.append(
            Hole(
                "ZRIB hanger screws",
                x,
                y,
                BASEBOARD.pilot_d,
                side=SIDE_UNDER,
                depth=WOOD_SCREW.length - WOOD_SCREW.boss_t,
                note="pilot for a 4 × 25 wood screw, blind: do not break through the top",
            )
        )
    for x, y in PSU_MOUNT.pilot_xy:
        holes.append(
            Hole(
                "PSU bracket screws",
                x,
                y,
                BASEBOARD.pilot_d,
                side=SIDE_UNDER,
                depth=WOOD_SCREW.length - WOOD_SCREW.boss_t,
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
    bx, by, _ = FRAME.board_size
    d = SvgDrawing(bx, by)
    thin = stroke("#000", 0.4)
    dashed = stroke("#06c", 0.4, "6 3")
    dotted = stroke("#888", 0.3, "2 2")

    d.rect(0, 0, bx, by, stroke("#000", 0.8, fill="#fff"))
    fx, fyy = FRAME.bed_origin
    d.rect(fx, fyy, fx + FRAME.bed_size[0], fyy + FRAME.bed_size[1], dotted)
    d.text(fx + 4, fyy + FRAME.bed_size[1] - 6, "bed panel (on the posts)", size=6)
    a3x, a3y = REQ.media_a3
    d.rect((bx - a3x) / 2, (by - a3y) / 2, (bx + a3x) / 2, (by + a3y) / 2, dotted, "A3 sheet")
    for ry in BASEBOARD.runner_y:
        d.rect(
            BASEBOARD.runner_x[0],
            ry - BASEBOARD.runner_w / 2,
            BASEBOARD.runner_x[1],
            ry + BASEBOARD.runner_w / 2,
            dashed,
        )
        d.text(BASEBOARD.runner_x[0] + 3, ry - BASEBOARD.runner_w / 2 - 3, "runner 2040 on edge (underside)", size=5)
    zc, zr = BASEBOARD.zrib_center, abs(ZMOUNT.plate_v[0])
    d.rect(
        zc[0] - ZMOUNT.leg_u[1],
        zc[1] - zr,
        zc[0] + ZMOUNT.leg_u[1],
        zc[1] + zr,
        dashed,
        "ZRIB mount (underside)",
    )
    for x in Y_AXIS.shaft_x:
        d.line(x, Y_AXIS.shaft_y0, x, Y_AXIS.shaft_y0 + 700, "#999", 0.4)
        for y in Y_AXIS.sk10_y:
            d.rect(
                x - SK10_SPEC.width / 2,
                y - SK10_SPEC.length / 2,
                x + SK10_SPEC.width / 2,
                y + SK10_SPEC.length / 2,
                thin,
            )
    for name, (x0, y0, x1, y1) in mount_zones().items():
        d.rect(x0, y0, x1, y1, 'fill="#fde9d0" fill-opacity="0.6" stroke="#c60" stroke-width="0.4"')
        d.text((x0 + x1) / 2, y1 + 4, f"{name}: not pre-drilled", anchor="middle", size=5)

    for y0 in LOOM.rail_starts:
        d.rect(
            LOOM.rail_x - LOOM.rail_t - LOOM.foot_w,
            y0,
            LOOM.rail_x,
            y0 + LOOM.rail_len,
            'fill="#dde8f5" stroke="#06c" stroke-width="0.4"',
        )
    d.text(
        LOOM.rail_x - 40,
        LOOM.rail_y0 - 8,
        "loom rails: not pre-drilled, wall 42 from the shaft",
        size=5,
    )
    for i, h in enumerate(board_holes(), 1):
        color = "#c00" if h.side == SIDE_TOP else "#06c"
        if h.countersink_d:
            d.circle(h.x, h.y, h.countersink_d / 2, stroke(color, 0.3))
        d.circle(h.x, h.y, h.d / 2, stroke(color, 0.5))
        d.crosshair(h.x, h.y, 6, color, 0.3)
        d.text(h.x + 5, h.y + 5, str(i), size=6)

    d.scale_bar(20, 20, 100)
    d.text(20, 22, "100 mm: print at 100 % and check this bar", size=6)
    d.text(
        8,
        by - 8,
        "Baseboard 700 × 900 × 18, top face, front-left corner = origin. "
        "Red: drill from the top. Blue: drill from the underside. Generated by "
        "`python -m plotzker layout`.",
        size=5,
    )
    return d.to_svg()


def hole_table() -> str:
    """Markdown table of the holes, numbered as in the drawing."""
    rows = []
    for i, h in enumerate(board_holes(), 1):
        notes = h.note
        if h.countersink_d:
            notes += f"; countersink Ø{h.countersink_d:g}"
        if h.depth:
            notes += f"; {h.depth:g} deep"
        rows.append((i, h.group, f"{h.x:g}", f"{h.y:g}", f"{h.d:g}", h.side, notes))
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
