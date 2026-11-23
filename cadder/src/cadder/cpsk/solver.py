"""Solving a CPSK sketch with FreeCAD's PlaneGCS solver (``planegcs``; RFC §7.3)."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import planegcs as gcs

from cpsk_core.errors import CpskSolveError, Diagnostic, Stage, error, warning
from cpsk_core.formula import Units
from cpsk_core.model import (
    Arc,
    Circle,
    Constraint,
    Geometry,
    Implicit,
    Line,
    Operand,
    Point,
    PointName,
    Primitive,
    Sketch,
)

_RESIDUAL = 1e-9
"""Largest constraint error accepted from a solve that ended as Converged."""


@dataclass(frozen=True)
class SolvedSketch:
    """A sketch with solved geometry, measured values and solve warnings."""

    sketch: Sketch
    primitives: tuple[Primitive, ...]
    measured: Mapping[str, float]
    """Values of identified non-driving constraints, in document units."""
    dof: int
    """Remaining degrees of freedom; 0 when fully constrained."""
    warnings: tuple[Diagnostic, ...] = ()

    @property
    def units(self) -> Units:
        """The document units."""
        return self.sketch.units

    def primitive(self, id: str) -> Primitive:
        """The solved primitive with this identifier."""
        for primitive in self.primitives:
            if primitive.id == id:
                return primitive
        raise KeyError(id)


@dataclass
class _Entity:
    """The planegcs objects behind one primitive or implicit reference."""

    points: dict[PointName | None, gcs.PointId] = field(default_factory=dict)
    line: gcs.LineId | None = None
    circle: gcs.CircleId | None = None
    arc: gcs.ArcId | None = None
    radius: gcs.ParamId | None = None
    angles: tuple[gcs.ParamId, gcs.ParamId] | None = None


@dataclass
class _Builder:
    """Translates a sketch into a planegcs system and reads the result back."""

    sketch: Sketch
    system: gcs.Sketch = field(default_factory=gcs.Sketch)
    entities: dict[int | Implicit, _Entity] = field(default_factory=dict)
    tags: dict[int, Constraint] = field(default_factory=dict)
    measured: dict[str, tuple[gcs.ParamId, bool]] = field(default_factory=dict)

    @property
    def units(self) -> Units:
        return self.sketch.units

    def param(self, value: float, fixed: bool) -> gcs.ParamId:
        return self.system.add_param(value, fixed=fixed)

    def point(self, x: float, y: float, fixed: bool) -> gcs.PointId:
        if not fixed:
            return self.system.add_point(x, y)
        return self.system.add_point_from_params(self.param(x, True), self.param(y, True))

    def line(self, start: Point, end: Point, fixed: bool) -> _Entity:
        p1 = self.point(start.x, start.y, fixed)
        p2 = self.point(end.x, end.y, fixed)
        return _Entity({"start": p1, "end": p2}, line=self.system.add_line(p1, p2))

    # ----- Geometry -----

    def add_geometry(self) -> None:
        blocked = {c.operands["of"].target for c in self.sketch.constraints if c.type == "block"}
        for primitive in self.sketch.primitives:
            self.entities[primitive.index] = self.entity(
                primitive.geometry, primitive.index in blocked
            )
        self.entities["origin"] = _Entity({None: self.point(0, 0, True)})
        self.entities["x_axis"] = self.line(Point(0, 0), Point(1, 0), True)
        self.entities["y_axis"] = self.line(Point(0, 0), Point(0, 1), True)

    def entity(self, geometry: Geometry, fixed: bool) -> _Entity:
        match geometry:
            case Point(x=x, y=y):
                return _Entity({None: self.point(x, y, fixed)})
            case Line():
                return self.line(geometry.start, geometry.end, fixed)
            case Circle(cx=cx, cy=cy, r=r):
                center = self.point(cx, cy, fixed)
                radius = self.param(r, fixed)
                circle = self.system.add_circle(center, radius)
                return _Entity({"center": center}, circle=circle, radius=radius)
            case Arc():
                center = self.point(geometry.cx, geometry.cy, fixed)
                start, end = geometry.start, geometry.end
                p_start = self.point(start.x, start.y, False)
                p_end = self.point(end.x, end.y, False)
                start_angle = self.units.to_radians(geometry.start_angle)
                radius = self.param(geometry.r, fixed)
                a1 = self.param(start_angle, fixed)
                a2 = self.param(start_angle + geometry.sweep, fixed)
                arc = self.system.add_arc(center, p_start, p_end, radius, a1, a2)
                points: dict[PointName | None, gcs.PointId] = {
                    "start": p_start,
                    "end": p_end,
                    "center": center,
                }
                return _Entity(points, arc=arc, radius=radius, angles=(a1, a2))
        raise AssertionError(geometry)

    # ----- Operands -----

    def pt(self, op: Operand) -> gcs.PointId:
        return self.entities[op.target].points[op.point]

    def ln(self, op: Operand) -> gcs.LineId:
        line = self.entities[op.target].line
        assert line is not None
        return line

    def curve(self, op: Operand) -> gcs.LineId | gcs.CircleId | gcs.ArcId:
        entity = self.entities[op.target]
        for found in (entity.line, entity.circle, entity.arc):
            if found is not None:
                return found
        raise AssertionError(op)

    def radius(self, op: Operand) -> gcs.ParamId:
        radius = self.entities[op.target].radius
        assert radius is not None
        return radius

    # ----- Constraints -----

    def add_constraints(self) -> None:
        for constraint in self.sketch.constraints:
            for tag in self.add(constraint):
                self.tags[int(tag)] = constraint

    def value(self, constraint: Constraint, *, angle: bool = False) -> gcs.ParamId:
        """The parameter holding a dimensional constraint's value (free when measured)."""
        value = constraint.value if constraint.driving else None
        if value is None:
            param = self.param(0.0, False)
            if constraint.id is not None:
                self.measured[constraint.id] = (param, angle)
            return param
        return self.param(self.units.to_radians(value) if angle else value, True)

    def add(self, c: Constraint) -> list[gcs.ConstraintTag]:
        s = self.system
        ops = c.operands
        driving = c.driving
        match c.type:
            case "coincident":
                return [s.coincident(self.pt(ops["a"]), self.pt(ops["b"]))]
            case "point-on":
                return [self.point_on(ops["point"], ops["object"])]
            case "horizontal" | "vertical":
                horizontal = c.type == "horizontal"
                if "of" in ops:
                    line = self.ln(ops["of"])
                    return [s.horizontal(line) if horizontal else s.vertical(line)]
                a, b = self.pt(ops["a"]), self.pt(ops["b"])
                return [s.horizontal_points(a, b) if horizontal else s.vertical_points(a, b)]
            case "parallel":
                return [s.parallel(self.ln(ops["a"]), self.ln(ops["b"]))]
            case "perpendicular":
                return [s.perpendicular(self.ln(ops["a"]), self.ln(ops["b"]))]
            case "tangent":
                return self.tangent(ops["a"], ops["b"])
            case "equal":
                if ops["a"].kind == "line":
                    return [s.equal_length(self.ln(ops["a"]), self.ln(ops["b"]))]
                return [s.equal(self.radius(ops["a"]), self.radius(ops["b"]))]
            case "symmetric":
                a, b = self.pt(ops["a"]), self.pt(ops["b"])
                if ops["about"].kind == "line":
                    return [s.symmetric_line(a, b, self.ln(ops["about"]))]
                return [s.symmetric_point(a, b, self.pt(ops["about"]))]
            case "block":
                return []
            case "distance":
                return [self.distance(c)]
            case "distance-x" | "distance-y":
                axis = 0 if c.type == "distance-x" else 1
                first = s.get_point_param_ids(self.pt(ops["a"]))[axis]
                second = s.get_point_param_ids(self.pt(ops["b"]))[axis]
                return [s.difference(first, second, self.value(c), driving=driving)]
            case "radius" | "diameter":
                return [self.size(c)]
            case _:
                if "of" in ops:
                    arc = self.entities[ops["of"].target].arc
                    assert arc is not None
                    return [s.arc_angle(arc, self.value(c, angle=True), driving=driving)]
                line_a, line_b = self.ln(ops["a"]), self.ln(ops["b"])
                return [s.l2l_angle(line_a, line_b, self.value(c, angle=True), driving=driving)]

    def point_on(self, point: Operand, obj: Operand) -> gcs.ConstraintTag:
        p = self.pt(point)
        entity = self.entities[obj.target]
        if entity.line is not None:
            return self.system.point_on_line(p, entity.line)
        if entity.circle is not None:
            return self.system.point_on_circle(p, entity.circle)
        assert entity.arc is not None
        return self.system.point_on_arc(p, entity.arc)

    def tangent(self, a: Operand, b: Operand) -> list[gcs.ConstraintTag]:
        s = self.system
        if a.is_point:
            # End point to end point: coincident, and the curves' tangents are parallel at the
            # joint. Like FreeCAD, keep the relative direction (0 or π) the stored shape has.
            curve_a = self.curve(replace(a, point=None))
            curve_b = self.curve(replace(b, point=None))
            joint = self.pt(a)
            angle = s.calculate_angle_via_point(curve_a, curve_b, joint)
            locked = 0.0 if math.cos(angle) >= 0 else math.pi
            return [
                s.coincident(joint, self.pt(b)),
                s.set_angle_via_point(curve_a, curve_b, joint, locked),
            ]
        if b.kind == "line":
            a, b = b, a
        ea, eb = self.entities[a.target], self.entities[b.target]
        if ea.line is not None:
            if eb.circle is not None:
                return [s.tangent_line_circle(ea.line, eb.circle)]
            assert eb.arc is not None
            return [s.tangent_line_arc(ea.line, eb.arc)]
        if ea.circle is not None and eb.circle is not None:
            return [s.tangent_circle_circle(ea.circle, eb.circle)]
        if ea.arc is not None and eb.arc is not None:
            return [s.tangent_arc_arc(ea.arc, eb.arc)]
        circle = ea.circle if ea.circle is not None else eb.circle
        arc = ea.arc if ea.arc is not None else eb.arc
        assert circle is not None and arc is not None
        return [s.tangent_circle_arc(circle, arc)]

    def distance(self, c: Constraint) -> gcs.ConstraintTag:
        s = self.system
        ops = c.operands
        value = self.value(c)
        if "of" in ops:
            entity = self.entities[ops["of"].target]
            start, end = entity.points["start"], entity.points["end"]
            return s.p2p_distance(start, end, value, driving=c.driving)
        a, b = ops["a"], ops["b"]
        if a.is_point and b.is_point:
            return s.p2p_distance(self.pt(a), self.pt(b), value, driving=c.driving)
        point, line = (a, b) if a.is_point else (b, a)
        return s.p2l_distance(self.pt(point), self.ln(line), value, driving=c.driving)

    def size(self, c: Constraint) -> gcs.ConstraintTag:
        s = self.system
        entity = self.entities[c.operands["of"].target]
        value = self.value(c)
        if entity.circle is not None:
            if c.type == "radius":
                return s.circle_radius(entity.circle, value, driving=c.driving)
            return s.circle_diameter(entity.circle, value, driving=c.driving)
        assert entity.arc is not None
        if c.type == "radius":
            return s.arc_radius(entity.arc, value, driving=c.driving)
        return s.arc_diameter(entity.arc, value, driving=c.driving)

    # ----- Results -----

    def labels(self, tags: list[gcs.ConstraintTag]) -> list[str]:
        found = dict.fromkeys(self.tags[int(t)].label for t in tags if int(t) in self.tags)
        return list(found)

    def solved(self, primitive: Primitive) -> Primitive:
        s = self.system
        entity = self.entities[primitive.index]
        geometry: Geometry
        match primitive.geometry:
            case Point():
                geometry = Point(*s.get_point(entity.points[None]))
            case Line():
                (x1, y1), (x2, y2) = (
                    s.get_point(entity.points["start"]),
                    s.get_point(entity.points["end"]),
                )
                geometry = Line(x1, y1, x2, y2)
            case Circle():
                assert entity.circle is not None
                info = s.get_circle(entity.circle)
                geometry = Circle(info.center[0], info.center[1], abs(info.radius))
            case Arc():
                assert entity.arc is not None
                arc = s.get_arc(entity.arc)
                start, sweep = arc.start_angle, arc.end_angle - arc.start_angle
                if arc.radius < 0:
                    start += math.pi
                if sweep < 0:
                    start, sweep = start + sweep, -sweep
                start = (start + math.pi) % math.tau - math.pi
                geometry = Arc(
                    arc.center[0],
                    arc.center[1],
                    abs(arc.radius),
                    self.units.from_radians(start),
                    self.units.from_radians(start + sweep),
                    units=self.units,
                )
        return replace(primitive, geometry=geometry)


def solve(sketch: Sketch, *, strict: bool = False) -> SolvedSketch:
    """Solve a sketch's constraints, starting from its stored coordinates.

    Raises :class:`CpskSolveError` for conflicting constraints or when the solver does not
    converge. Remaining degrees of freedom and redundant constraints are warnings; with
    ``strict`` they are errors too.
    """
    builder = _Builder(sketch)
    builder.add_geometry()
    builder.add_constraints()
    status = builder.system.solve()
    diagnosis = builder.system.diagnose()
    if diagnosis.conflicting:
        ids = builder.labels(diagnosis.conflicting)
        message = f"conflicting constraints: {', '.join(ids)}"
        raise CpskSolveError([error(Stage.SOLVE, "conflicting", message, ids=ids)])
    # Redundant constraints make the solver report Converged rather than Success, also when
    # every constraint is met; accept that when the residuals are negligible.
    satisfied = status == gcs.SolveStatus.Converged and all(
        builder.system.constraint_error(gcs.ConstraintTag(tag)) < _RESIDUAL for tag in builder.tags
    )
    if status != gcs.SolveStatus.Success and not satisfied:
        message = f"the solver did not converge ({status.name})"
        raise CpskSolveError([error(Stage.SOLVE, "solve-failed", message)])

    warnings: list[Diagnostic] = []
    if diagnosis.dof > 0:
        message = f"under-constrained: {diagnosis.dof} degrees of freedom remain"
        warnings.append(warning(Stage.SOLVE, "degrees-of-freedom", message))
    for code, tags in (
        ("redundant", diagnosis.redundant),
        ("partially-redundant", diagnosis.partially_redundant),
    ):
        if tags:
            ids = builder.labels(tags)
            message = f"{code.replace('-', ' ')} constraints: {', '.join(ids)}"
            warnings.append(warning(Stage.SOLVE, code, message, ids=ids))

    measured = {
        id: builder.units.from_radians(builder.system.get_param(param))
        if angle
        else builder.system.get_param(param)
        for id, (param, angle) in builder.measured.items()
    }
    if strict and warnings:
        raise CpskSolveError(warnings)
    return SolvedSketch(
        sketch=sketch,
        primitives=tuple(builder.solved(p) for p in sketch.primitives),
        measured=measured,
        dof=diagnosis.dof,
        warnings=tuple(warnings),
    )
