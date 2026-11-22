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

from plotzker.hardware import SK10
from plotzker.params import (
    BASEBOARD,
    FRAME,
    LOOM,
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
    bb = BASEBOARD
    m5 = TOL.bolt_hole_d(5)
    holes: list[Hole] = []
    for rail, shaft_x in enumerate(Y_AXIS.shaft_x):
        floating = rail == 1
        for y in Y_AXIS.sk10_y:
            for dx in bb.sk10_hole_x:
                holes.append(
                    Hole(
                        f"SK10, {'right (oversized)' if floating else 'left (fixed)'} rail",
                        shaft_x + dx,
                        y,
                        bb.sk10_float_hole_d if floating else m5,
                        note="M5 bolt, nut + washer underneath",
                    )
                )
    for ry in bb.runner_y:
        for x in bb.runner_screw_x:
            holes.append(
                Hole(
                    "Runner screws",
                    x,
                    ry,
                    m5,
                    countersink_d=bb.runner_screw_head_d + 2 * TOL.bolt,
                    note="M5 countersunk into a T-nut in the runner",
                )
            )
    for x, y in bb.post_xy:
        holes.append(Hole("Bed posts", x, y, m5, note="M5 stud, head under the board"))
    holes.append(
        Hole("Loom hole", LOOM.hole_x, LOOM.hole_y, LOOM.hole_d, note="Y loom to the ZRIB; deburr")
    )
    for x, y in bb.zrib_pilot_xy:
        holes.append(
            Hole(
                "ZRIB hanger screws",
                x,
                y,
                bb.pilot_d,
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
    bb = BASEBOARD

    def fy(y: float) -> float:
        """SVG y (down) from machine y (up)."""
        return by - y

    out: list[str] = []

    def rect(x0: float, y0: float, x1: float, y1: float, style: str, label: str = "") -> None:
        out.append(
            f'<rect x="{x0:g}" y="{fy(y1):g}" width="{x1 - x0:g}" height="{y1 - y0:g}" {style}/>'
        )
        if label:
            text((x0 + x1) / 2, (y0 + y1) / 2, label, anchor="middle", size=7)

    def text(x: float, y: float, s: str, anchor: str = "start", size: float = 6) -> None:
        out.append(
            f'<text x="{x:g}" y="{fy(y):g}" font-size="{size:g}" text-anchor="{anchor}" '
            f'font-family="Helvetica, Arial, sans-serif" fill="#222">{s}</text>'
        )

    thin = 'fill="none" stroke="#000" stroke-width="0.4"'
    dashed = 'fill="none" stroke="#06c" stroke-width="0.4" stroke-dasharray="6 3"'
    dotted = 'fill="none" stroke="#888" stroke-width="0.3" stroke-dasharray="2 2"'

    rect(0, 0, bx, by, 'fill="#fff" stroke="#000" stroke-width="0.8"')
    fx, fyy = FRAME.bed_origin
    rect(fx, fyy, fx + FRAME.bed_size[0], fyy + FRAME.bed_size[1], dotted)
    text(fx + 4, fyy + FRAME.bed_size[1] - 6, "bed panel (on the posts)", size=6)
    a3x, a3y = REQ.media_a3
    rect((bx - a3x) / 2, (by - a3y) / 2, (bx + a3x) / 2, (by + a3y) / 2, dotted, "A3 sheet")
    for ry in bb.runner_y:
        rect(
            bb.runner_x[0],
            ry - bb.runner_w / 2,
            bb.runner_x[1],
            ry + bb.runner_w / 2,
            dashed,
        )
        text(
            bb.runner_x[0] + 3, ry - bb.runner_w / 2 - 3, "runner 2040 on edge (underside)", size=5
        )
    zc, zr = bb.zrib_center, abs(ZMOUNT.plate_v[0])
    rect(
        zc[0] - ZMOUNT.leg_u[1],
        zc[1] - zr,
        zc[0] + ZMOUNT.leg_u[1],
        zc[1] + zr,
        dashed,
        "ZRIB mount (underside)",
    )
    for x in Y_AXIS.shaft_x:
        out.append(
            f'<line x1="{x:g}" y1="{fy(Y_AXIS.shaft_y0):g}" x2="{x:g}" '
            f'y2="{fy(Y_AXIS.shaft_y0 + 700):g}" stroke="#999" stroke-width="0.4"/>'
        )
        for y in Y_AXIS.sk10_y:
            rect(
                x - SK10.width / 2,
                y - SK10.length / 2,
                x + SK10.width / 2,
                y + SK10.length / 2,
                thin,
            )
    for name, (x0, y0, x1, y1) in mount_zones().items():
        rect(x0, y0, x1, y1, 'fill="#fde9d0" fill-opacity="0.6" stroke="#c60" stroke-width="0.4"')
        text((x0 + x1) / 2, y1 + 4, f"{name}: not pre-drilled", anchor="middle", size=5)

    for y0 in LOOM.rail_starts:
        rect(
            LOOM.rail_x - LOOM.rail_t - LOOM.foot_w,
            y0,
            LOOM.rail_x,
            y0 + LOOM.rail_len,
            'fill="#dde8f5" stroke="#06c" stroke-width="0.4"',
        )
    text(
        LOOM.rail_x - 40,
        LOOM.rail_y0 - 8,
        "loom rails: not pre-drilled, wall 42 from the shaft",
        size=5,
    )
    holes = board_holes()
    for i, h in enumerate(holes, 1):
        color = "#c00" if h.side == SIDE_TOP else "#06c"
        if h.countersink_d:
            out.append(
                f'<circle cx="{h.x:g}" cy="{fy(h.y):g}" r="{h.countersink_d / 2:g}" '
                f'fill="none" stroke="{color}" stroke-width="0.3"/>'
            )
        out.append(
            f'<circle cx="{h.x:g}" cy="{fy(h.y):g}" r="{h.d / 2:g}" fill="none" '
            f'stroke="{color}" stroke-width="0.5"/>'
        )
        out.append(
            f'<path d="M{h.x - 6:g},{fy(h.y):g}H{h.x + 6:g}'
            f'M{h.x:g},{fy(h.y) - 6:g}V{fy(h.y) + 6:g}" '
            f'stroke="{color}" stroke-width="0.3"/>'
        )
        text(h.x + 5, h.y + 5, str(i), size=6)

    out.append(
        f'<path d="M20,{by - 20:g}h100" stroke="#000" stroke-width="1"/>'
        f'<path d="M20,{by - 24:g}v8M120,{by - 24:g}v8" stroke="#000" stroke-width="1"/>'
    )
    text(20, 22, "100 mm: print at 100 % and check this bar", size=6)
    text(
        8,
        by - 8,
        "Baseboard 700 × 900 × 18, top face, front-left corner = origin. "
        "Red: drill from the top. Blue: drill from the underside. Generated by "
        "`python -m plotzker layout`.",
        size=5,
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{bx:g}mm" height="{by:g}mm" '
        f'viewBox="0 0 {bx:g} {by:g}">\n' + "\n".join(out) + "\n</svg>\n"
    )


def hole_table() -> str:
    """Markdown table of the holes, numbered as in the drawing."""
    rows = [
        "| # | Group | x | y | Ø | Face | Notes |",
        "|---|-------|---|---|---|------|-------|",
    ]
    for i, h in enumerate(board_holes(), 1):
        notes = h.note
        if h.countersink_d:
            notes += f"; countersink Ø{h.countersink_d:g}"
        if h.depth:
            notes += f"; {h.depth:g} deep"
        rows.append(f"| {i} | {h.group} | {h.x:g} | {h.y:g} | {h.d:g} | {h.side} | {notes} |")
    return "\n".join(rows)


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
