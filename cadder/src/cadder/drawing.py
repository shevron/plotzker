"""2D drawings for the workshop: 1:1 SVG sheets (drilling templates, cutting layouts) and
Markdown tables.

:class:`SvgDrawing` draws in model millimetres with y pointing **up** (the model's frame seen
from above) and writes an SVG whose user unit is 1 mm and whose printed size is the sheet's
size in mm, so it prints at 1:1. Styles are SVG presentation attributes; :func:`stroke` builds
the common ones.
"""

from collections.abc import Iterable, Sequence

#: Font of all text
FONT = "Helvetica, Arial, sans-serif"
#: Text color
INK = "#222"


def stroke(
    color: str = "#000", width: float = 0.4, dash: str | None = None, fill: str = "none"
) -> str:
    """SVG attributes of an outline: ``fill``, ``stroke``, ``stroke-width`` and an optional
    ``stroke-dasharray``."""
    style = f'fill="{fill}" stroke="{color}" stroke-width="{width:g}"'
    return style + (f' stroke-dasharray="{dash}"' if dash else "")


class SvgDrawing:
    """An SVG sheet of ``width`` × ``height`` mm; coordinates in mm with y up, origin at the
    bottom-left corner."""

    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height
        self.elements: list[str] = []

    def y(self, y: float) -> float:
        """SVG y (down from the top edge) of model y (up from the bottom edge)."""
        return self.height - y

    def raw(self, element: str) -> None:
        """Add an SVG element as is (in SVG coordinates)."""
        self.elements.append(element)

    def rect(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        style: str,
        label: str = "",
        label_size: float = 7,
    ) -> None:
        """A rectangle between two corners, with an optional label centered in it."""
        self.raw(
            f'<rect x="{x0:g}" y="{self.y(y1):g}" width="{x1 - x0:g}" height="{y1 - y0:g}" '
            f"{style}/>"
        )
        if label:
            self.text((x0 + x1) / 2, (y0 + y1) / 2, label, anchor="middle", size=label_size)

    def text(self, x: float, y: float, s: str, anchor: str = "start", size: float = 6) -> None:
        """Text with its baseline at ``(x, y)``; ``anchor``: start, middle or end."""
        self.raw(
            f'<text x="{x:g}" y="{self.y(y):g}" font-size="{size:g}" text-anchor="{anchor}" '
            f'font-family="{FONT}" fill="{INK}">{s}</text>'
        )

    def line(
        self, x1: float, y1: float, x2: float, y2: float, color: str = "#000", width: float = 0.4
    ) -> None:
        """A straight line."""
        self.raw(
            f'<line x1="{x1:g}" y1="{self.y(y1):g}" x2="{x2:g}" y2="{self.y(y2):g}" '
            f'stroke="{color}" stroke-width="{width:g}"/>'
        )

    def circle(self, x: float, y: float, r: float, style: str) -> None:
        """A circle of radius ``r``."""
        self.raw(f'<circle cx="{x:g}" cy="{self.y(y):g}" r="{r:g}" {style}/>')

    def crosshair(
        self, x: float, y: float, half: float = 6, color: str = "#000", width: float = 0.3
    ) -> None:
        """A center mark: a cross of arms ``half`` long."""
        cy = self.y(y)
        self.raw(
            f'<path d="M{x - half:g},{cy:g}H{x + half:g}M{x:g},{cy - half:g}V{cy + half:g}" '
            f'stroke="{color}" stroke-width="{width:g}"/>'
        )

    def scale_bar(self, x: float, y: float, length: float = 100, tick: float = 4) -> None:
        """A bar ``length`` mm long with end ticks, to check the printed scale."""
        cy = self.y(y)
        self.raw(
            f'<path d="M{x:g},{cy:g}h{length:g}" stroke="#000" stroke-width="1"/>'
            f'<path d="M{x:g},{cy - tick:g}v{2 * tick:g}M{x + length:g},{cy - tick:g}'
            f'v{2 * tick:g}" stroke="#000" stroke-width="1"/>'
        )

    def to_svg(self) -> str:
        """The whole document."""
        w, h = self.width, self.height
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}mm" height="{h:g}mm" '
            f'viewBox="0 0 {w:g} {h:g}">\n' + "\n".join(self.elements) + "\n</svg>\n"
        )


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """A Markdown table; values are written with ``str`` (floats with ``:g``)."""

    def cell(value: object) -> str:
        return f"{value:g}" if isinstance(value, float) else str(value)

    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("-" * max(3, len(h) + 2) for h in headers) + "|",
    ]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)
