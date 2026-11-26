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
            self.entities[primitive.index] = self.entity(primitive.geometry, primitive.index in blocked)
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

    def point_id(self, operand: Operand) -> gcs.PointId:
        return self.entities[operand.target].points[operand.point]

    def line_id(self, operand: Operand) -> gcs.LineId:
        line = self.entities[operand.target].line
        assert line is not None
        return line

    def curve(self, operand: Operand) -> gcs.LineId | gcs.CircleId | gcs.ArcId:
        entity = self.entities[operand.target]
        for found in (entity.line, entity.circle, entity.arc):
            if found is not None:
                return found
        raise AssertionError(operand)

    def radius(self, operand: Operand) -> gcs.ParamId:
        radius = self.entities[operand.target].radius
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

    def add(self, constraint: Constraint) -> list[gcs.ConstraintTag]:
        system = self.system
        ops = constraint.operands
        driving = constraint.driving
        match constraint.type:
            case "coincident":
                return [system.coincident(self.point_id(ops["a"]), self.point_id(ops["b"]))]
            case "point-on":
                return [self.point_on(ops["point"], ops["object"])]
            case "horizontal" | "vertical":
                horizontal = constraint.type == "horizontal"
                if "of" in ops:
                    line = self.line_id(ops["of"])
                    return [system.horizontal(line) if horizontal else system.vertical(line)]
                a, b = self.point_id(ops["a"]), self.point_id(ops["b"])
                return [system.horizontal_points(a, b) if horizontal else system.vertical_points(a, b)]
            case "parallel":
                return [system.parallel(self.line_id(ops["a"]), self.line_id(ops["b"]))]
            case "perpendicular":
                return self.perpendicular(ops["a"], ops["b"])
            case "tangent":
                return self.tangent(ops["a"], ops["b"])
            case "equal":
                if ops["a"].kind == "line":
                    return [system.equal_length(self.line_id(ops["a"]), self.line_id(ops["b"]))]
                return [system.equal(self.radius(ops["a"]), self.radius(ops["b"]))]
            case "symmetric":
                a, b = self.point_id(ops["a"]), self.point_id(ops["b"])
                if ops["about"].kind == "line":
                    return [system.symmetric_line(a, b, self.line_id(ops["about"]))]
                return [system.symmetric_point(a, b, self.point_id(ops["about"]))]
            case "block":
                return []
            case "distance":
                return [self.distance(constraint)]
            case "distance-x" | "distance-y":
                axis = 0 if constraint.type == "distance-x" else 1
                first = system.get_point_param_ids(self.point_id(ops["a"]))[axis]
                second = system.get_point_param_ids(self.point_id(ops["b"]))[axis]
                return [system.difference(first, second, self.value(constraint), driving=driving)]
            case "radius" | "diameter":
                return [self.size(constraint)]
            case _:
                if "of" in ops:
                    arc = self.entities[ops["of"].target].arc
                    assert arc is not None
                    return [system.arc_angle(arc, self.value(constraint, angle=True), driving=driving)]
                line_a, line_b = self.line_id(ops["a"]), self.line_id(ops["b"])
                return [system.l2l_angle(line_a, line_b, self.value(constraint, angle=True), driving=driving)]

    def point_on(self, point: Operand, obj: Operand) -> gcs.ConstraintTag:
        p = self.point_id(point)
        entity = self.entities[obj.target]
        if entity.line is not None:
            return self.system.point_on_line(p, entity.line)
        if entity.circle is not None:
            return self.system.point_on_circle(p, entity.circle)
        assert entity.arc is not None
        return self.system.point_on_arc(p, entity.arc)

    def perpendicular(self, a: Operand, b: Operand) -> list[gcs.ConstraintTag]:
        system = self.system
        if a.is_point:
            # End points of a line and an arc: coincident, and the curves are perpendicular at
            # the joint. Like FreeCAD, keep the side (+90° or -90°) the stored shape has.
            curve_a = self.curve(replace(a, point=None))
            curve_b = self.curve(replace(b, point=None))
            joint = self.point_id(a)
            angle = system.calculate_angle_via_point(curve_a, curve_b, joint)
            locked = math.pi / 2 if math.sin(angle) >= 0 else -math.pi / 2
            return [
                system.coincident(joint, self.point_id(b)),
                system.set_angle_via_point(curve_a, curve_b, joint, locked),
            ]
        if a.kind == "line" and b.kind == "line":
            return [system.perpendicular(self.line_id(a), self.line_id(b))]
        line, curve = (a, b) if a.kind == "line" else (b, a)
        center = self.point_id(replace(curve, point="center", kind="point"))
        return [system.point_on_line(center, self.line_id(line))]  # normal to the curve

    def tangent(self, a: Operand, b: Operand) -> list[gcs.ConstraintTag]:
        system = self.system
        if a.is_point:
            # End point to end point: coincident, and the curves' tangents are parallel at the
            # joint. Like FreeCAD, keep the relative direction (0 or π) the stored shape has.
            curve_a = self.curve(replace(a, point=None))
            curve_b = self.curve(replace(b, point=None))
            joint = self.point_id(a)
            angle = system.calculate_angle_via_point(curve_a, curve_b, joint)
            locked = 0.0 if math.cos(angle) >= 0 else math.pi
            return [
                system.coincident(joint, self.point_id(b)),
                system.set_angle_via_point(curve_a, curve_b, joint, locked),
            ]
        if b.kind == "line":
            a, b = b, a
        entity_a, entity_b = self.entities[a.target], self.entities[b.target]
        if entity_a.line is not None:
            if entity_b.circle is not None:
                return [system.tangent_line_circle(entity_a.line, entity_b.circle)]
            assert entity_b.arc is not None
            return [system.tangent_line_arc(entity_a.line, entity_b.arc)]
        if entity_a.circle is not None and entity_b.circle is not None:
            return [system.tangent_circle_circle(entity_a.circle, entity_b.circle)]
        if entity_a.arc is not None and entity_b.arc is not None:
            return [system.tangent_arc_arc(entity_a.arc, entity_b.arc)]
        circle = entity_a.circle if entity_a.circle is not None else entity_b.circle
        arc = entity_a.arc if entity_a.arc is not None else entity_b.arc
        assert circle is not None and arc is not None
        return [system.tangent_circle_arc(circle, arc)]

    def distance(self, constraint: Constraint) -> gcs.ConstraintTag:
        system = self.system
        ops = constraint.operands
        value = self.value(constraint)
        if "of" in ops:
            entity = self.entities[ops["of"].target]
            start, end = entity.points["start"], entity.points["end"]
            return system.p2p_distance(start, end, value, driving=constraint.driving)
        a, b = ops["a"], ops["b"]
        if a.is_point and b.is_point:
            return system.p2p_distance(self.point_id(a), self.point_id(b), value, driving=constraint.driving)
        point, line = (a, b) if a.is_point else (b, a)
        return system.p2l_distance(self.point_id(point), self.line_id(line), value, driving=constraint.driving)

    def size(self, constraint: Constraint) -> gcs.ConstraintTag:
        system = self.system
        entity = self.entities[constraint.operands["of"].target]
        value = self.value(constraint)
        if entity.circle is not None:
            if constraint.type == "radius":
                return system.circle_radius(entity.circle, value, driving=constraint.driving)
            return system.circle_diameter(entity.circle, value, driving=constraint.driving)
        assert entity.arc is not None
        if constraint.type == "radius":
            return system.arc_radius(entity.arc, value, driving=constraint.driving)
        return system.arc_diameter(entity.arc, value, driving=constraint.driving)

    # ----- Results -----

    def labels(self, tags: list[gcs.ConstraintTag]) -> list[str]:
        found = dict.fromkeys(self.tags[int(t)].label for t in tags if int(t) in self.tags)
        return list(found)

    def solved(self, primitive: Primitive) -> Primitive:
        system = self.system
        entity = self.entities[primitive.index]
        geometry: Geometry
        match primitive.geometry:
            case Point():
                geometry = Point(*system.get_point(entity.points[None]))
            case Line():
                (x1, y1), (x2, y2) = (
                    system.get_point(entity.points["start"]),
                    system.get_point(entity.points["end"]),
                )
                geometry = Line(x1, y1, x2, y2)
            case Circle():
                assert entity.circle is not None
                info = system.get_circle(entity.circle)
                geometry = Circle(info.center[0], info.center[1], abs(info.radius))
            case Arc():
                assert entity.arc is not None
                arc = system.get_arc(entity.arc)
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
        id: builder.units.from_radians(builder.system.get_param(param)) if angle else builder.system.get_param(param)
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
