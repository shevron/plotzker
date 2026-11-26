"""Export of a solved CPSK sketch as an SVG profile for ``cadder.geometry.load_sketch``."""

import math
from dataclasses import dataclass
from xml.sax.saxutils import escape

from cadder.cpsk.solver import SolvedSketch
from cpsk_core.errors import CpskExportError, Stage, error
from cpsk_core.model import Arc, Circle, Line, Point, Primitive


@dataclass(frozen=True)
class _Edge:
    """A line or arc of the profile, in millimeters."""

    primitive: Primitive
    start: Point
    end: Point


def to_svg(solved: SolvedSketch, *, allow_open: bool = False) -> str:
    """The sketch's non-construction geometry as an SVG document, 1 user unit = 1 mm.

    Lines and arcs are chained into closed loops by their end points; the loops and circles
    form one ``<path>`` with ``fill-rule="evenodd"``, so inner loops are holes. This follows
    the conventions of :func:`cadder.geometry.load_sketch`: y points up in the sketch and down
    in SVG, and the viewBox's bottom-left corner is the origin of the loaded profile. That
    corner is (min(0, min x), min(0, min y)), so geometry with negative coordinates is loaded
    shifted by that amount; other geometry keeps its coordinates.

    Geometry that does not form closed loops (open wires, branches) raises
    :class:`CpskExportError`; with ``allow_open`` it is drawn as an unfilled stroke instead.
    Points are not exported.
    """
    scale = solved.units.to_mm(1.0)
    primitives = [p for p in solved.primitives if not p.construction]
    circles = [p for p in primitives if isinstance(p.geometry, Circle)]
    edges = [_edge(p, solved) for p in primitives if isinstance(p.geometry, Line | Arc)]
    loops, open_edges = _loops(edges, scale)
    if open_edges and not allow_open:
        labels = list(dict.fromkeys(edge.primitive.label for edge in open_edges))
        message = f"geometry does not form closed loops: {', '.join(labels)}"
        raise CpskExportError([error(Stage.EXPORT, "open-wire", message, ids=labels)])

    _, _, xmax, ymax = _bounds(primitives, scale)
    left, bottom = svg_origin(solved)
    top = max(0.0, ymax)
    width, height = max(0.0, xmax) - left, top - bottom

    def xy(point: Point) -> str:
        return f"{_n(point.x)} {_n(top - point.y)}"

    def segment(edge: _Edge, forward: bool) -> str:
        end = edge.end if forward else edge.start
        geometry = edge.primitive.geometry
        if isinstance(geometry, Line):
            return f"L {xy(end)}"
        assert isinstance(geometry, Arc)
        radius = _n(geometry.r * scale)
        large = int(geometry.sweep > math.pi)
        return f"A {radius} {radius} 0 {large} {0 if forward else 1} {xy(end)}"

    filled: list[str] = []
    for loop in loops:
        first, forward = loop[0]
        commands = [f"M {xy(first.start if forward else first.end)}"]
        commands += [segment(edge, forward) for edge, forward in loop]
        filled.append(" ".join(commands) + " Z")
    for primitive in circles:
        circle = primitive.geometry
        assert isinstance(circle, Circle)
        cx, cy, radius = circle.cx * scale, circle.cy * scale, circle.r * scale
        east, west = Point(cx + radius, cy), Point(cx - radius, cy)
        filled.append(
            f"M {xy(east)} A {_n(radius)} {_n(radius)} 0 1 0 {xy(west)} A {_n(radius)} {_n(radius)} 0 1 0 {xy(east)} Z"
        )
    stroked = [f"M {xy(e.start)} {segment(e, True)}" for e in open_edges]

    title = solved.sketch.metadata.get("title", ("",))[0]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(width)}mm" height="{_n(height)}mm"'
        f' viewBox="{_n(left)} 0 {_n(width)} {_n(height)}">',
    ]
    if title:
        lines.append(f"  <title>{escape(title)}</title>")
    if filled:
        lines.append(f'  <path fill="black" fill-rule="evenodd" d="{" ".join(filled)}"/>')
    if stroked:
        lines.append(f'  <path fill="none" stroke="black" stroke-width="0.2" d="{" ".join(stroked)}"/>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def svg_origin(solved: SolvedSketch) -> tuple[float, float]:
    """The sketch point, in mm, at the bottom-left corner of :func:`to_svg`'s viewBox.

    :func:`cadder.geometry.load_sketch` places this point at its origin; it is (0, 0) unless
    the geometry has negative coordinates.
    """
    scale = solved.units.to_mm(1.0)
    primitives = [p for p in solved.primitives if not p.construction]
    xmin, ymin, _, _ = _bounds(primitives, scale)
    return min(0.0, xmin), min(0.0, ymin)


def _edge(primitive: Primitive, solved: SolvedSketch) -> _Edge:
    geometry = primitive.geometry
    assert isinstance(geometry, Line | Arc)
    scale = solved.units.to_mm(1.0)
    start, end = geometry.start, geometry.end
    return _Edge(
        primitive,
        Point(start.x * scale, start.y * scale),
        Point(end.x * scale, end.y * scale),
    )


def _loops(edges: list[_Edge], scale: float) -> tuple[list[list[tuple[_Edge, bool]]], list[_Edge]]:
    """Closed loops (edges with their direction) and the edges that are not in one."""
    extent = max((abs(c) for e in edges for p in (e.start, e.end) for c in (p.x, p.y)), default=1.0)
    tolerance = 1e-6 * max(1.0, extent)
    vertices: list[Point] = []

    def vertex(point: Point) -> int:
        for index, other in enumerate(vertices):
            if math.dist((point.x, point.y), (other.x, other.y)) <= tolerance:
                return index
        vertices.append(point)
        return len(vertices) - 1

    ends = [(vertex(e.start), vertex(e.end)) for e in edges]
    incident: dict[int, list[int]] = {}
    for index, (a, b) in enumerate(ends):
        incident.setdefault(a, []).append(index)
        incident.setdefault(b, []).append(index)

    component: dict[int, int] = {}
    for start in range(len(edges)):
        if start in component:
            continue
        stack = [start]
        while stack:
            index = stack.pop()
            if index in component:
                continue
            component[index] = start
            for v in ends[index]:
                stack.extend(incident[v])
    bad = {component[i] for v, items in incident.items() if len(items) != 2 for i in items}
    open_edges = [e for i, e in enumerate(edges) if component[i] in bad]

    loops: list[list[tuple[_Edge, bool]]] = []
    used: set[int] = set()
    for first in range(len(edges)):
        if first in used or component[first] in bad:
            continue
        loop: list[tuple[_Edge, bool]] = []
        index, at = first, ends[first][0]
        while index not in used:
            used.add(index)
            a, b = ends[index]
            forward = a == at
            loop.append((edges[index], forward))
            at = b if forward else a
            index = next((i for i in incident[at] if i != index), index)
        loops.append(loop)
    return loops, open_edges


def _bounds(primitives: list[Primitive], scale: float) -> tuple[float, float, float, float]:
    """The bounding box of the geometry, in millimeters."""
    points: list[Point] = []
    for primitive in primitives:
        geometry = primitive.geometry
        match geometry:
            case Point():
                continue
            case Line():
                points += [geometry.start, geometry.end]
            case Circle(cx=cx, cy=cy, r=r):
                points += [Point(cx - r, cy - r), Point(cx + r, cy + r)]
            case Arc():
                points += [geometry.start, geometry.end]
                start = geometry.units.to_radians(geometry.start_angle)
                for quarter in range(4):
                    angle = quarter * math.pi / 2
                    if (angle - start) % math.tau <= geometry.sweep:
                        points.append(
                            Point(
                                geometry.cx + geometry.r * math.cos(angle),
                                geometry.cy + geometry.r * math.sin(angle),
                            )
                        )
    if not points:
        return 0.0, 0.0, 0.0, 0.0
    xs = [p.x * scale for p in points]
    ys = [p.y * scale for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _n(value: float) -> str:
    """A coordinate, without needless digits."""
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text
