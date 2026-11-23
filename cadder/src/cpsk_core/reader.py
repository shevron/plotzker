"""Compiling CPSK documents into sketches: structure, references, nesting, formulas."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias, cast

from cpsk_core.document import NAMESPACE, Document, Element
from cpsk_core.document import parse as parse_document
from cpsk_core.errors import CpskLoadError, Diagnostic, Severity, Stage, error, warning
from cpsk_core.formula import (
    ANGLE_UNITS,
    CONSTANTS,
    FUNCTIONS,
    IDENTIFIER_RE,
    LENGTH_UNITS,
    NUMBER_RE,
    UNITS,
    FormulaError,
    Name,
    Node,
    Number,
    Units,
    evaluate,
    parse,
    parse_literal,
    unit_kind,
)
from cpsk_core.model import (
    IMPLICIT,
    POINTS,
    Arc,
    Circle,
    Constraint,
    Geometry,
    Implicit,
    Kind,
    Line,
    Operand,
    Point,
    Primitive,
    Sketch,
)

VERSION = (0, 1)
"""The format version this reader implements."""

RESERVED = frozenset(IMPLICIT) | {"self"} | frozenset(CONSTANTS) | FUNCTIONS | UNITS
"""Words that cannot be identifiers (spec §3.2)."""

Overrides: TypeAlias = Mapping[str, float | str]
ValueKind: TypeAlias = Literal["number", "length", "angle"]

_CONTAINERS = ("metadata", "variables", "geometry", "constraints")
_METADATA = frozenset({"title", "description", "author", "created", "modified", "tag"})
_GEOMETRY_ATTRS: dict[str, tuple[str, ...]] = {
    "point": ("x", "y"),
    "line": ("x1", "y1", "x2", "y2"),
    "circle": ("cx", "cy", "r"),
    "arc": ("cx", "cy", "r", "start-angle", "end-angle"),
}
OPERANDS: dict[str, tuple[str, ...]] = {
    "coincident": ("a", "b"),
    "point-on": ("point", "object"),
    "horizontal": ("of", "a", "b"),
    "vertical": ("of", "a", "b"),
    "parallel": ("a", "b"),
    "perpendicular": ("a", "b"),
    "tangent": ("a", "b"),
    "equal": ("a", "b"),
    "symmetric": ("a", "b", "about"),
    "block": ("of",),
    "distance": ("of", "a", "b"),
    "distance-x": ("a", "b"),
    "distance-y": ("a", "b"),
    "radius": ("of",),
    "diameter": ("of",),
    "angle": ("of", "a", "b"),
}
"""Each constraint type's operand attributes (spec §9.3)."""
_DIMENSIONS: dict[str, Literal["length", "angle"]] = {
    "distance": "length",
    "distance-x": "length",
    "distance-y": "length",
    "radius": "length",
    "diameter": "length",
    "angle": "angle",
}
_SINGLE = frozenset({"block", "radius", "diameter"})
"""Constraints whose only operand is ``of``."""
_OF_OR_PAIR = frozenset({"horizontal", "vertical", "distance", "angle"})
"""Constraints written either with ``of`` or with ``a`` and ``b``."""


# ----- Reader -----


@dataclass
class _Variable:
    id: str
    type: ValueKind
    formula: Node | None
    low: float | None
    high: float | None
    line: int | None


@dataclass
class _RawConstraint:
    type: str
    attrs: dict[str, str]
    line: int | None
    parent: int | None
    element: Element | None = None
    formula: Node | None = None

    @property
    def id(self) -> str | None:
        return self.attrs.get("id")

    @property
    def driving(self) -> bool:
        return self.attrs.get("driving") != "false"


class _ReferenceFailedError(Exception):
    """A reference in a formula failed; the problem is already reported."""


@dataclass
class _Reader:
    """Reads one document; collects diagnostics instead of stopping at the first error."""

    overrides: Overrides
    diagnostics: list[Diagnostic] = field(default_factory=list)
    version: str = ""
    units: Units = field(default_factory=Units)
    ids: dict[str, int | None] = field(default_factory=dict)
    metadata: dict[str, list[str]] = field(default_factory=dict)
    variables: dict[str, _Variable] = field(default_factory=dict)
    primitives: list[Primitive] = field(default_factory=list)
    raws: list[_RawConstraint] = field(default_factory=list)

    # ----- Reporting and attribute helpers -----

    def error(self, code: str, message: str, line: int | None, ids: tuple[str, ...] = ()) -> None:
        self.diagnostics.append(error(Stage.LOAD, code, message, ids=ids, line=line))

    def warn(self, code: str, message: str, line: int | None) -> None:
        self.diagnostics.append(warning(Stage.LOAD, code, message, line=line))

    def unknown(self, element: Element) -> None:
        self.warn("unknown-content", f"unknown element <{element.name}> ignored", element.line)

    def check_attrs(self, element: Element, allowed: tuple[str, ...]) -> None:
        for namespace, name in element.attrs:
            if namespace == NAMESPACE or (namespace is None and name not in allowed):
                message = f"unknown attribute {name!r} on <{element.name}> ignored"
                self.warn("unknown-content", message, element.line)

    def required(self, element: Element, name: str) -> str | None:
        value = element.get(name)
        if value is None:
            self.error("structure", f"<{element.name}> needs a {name!r} attribute", element.line)
        return value

    def register_id(self, id: str | None, line: int | None) -> str | None:
        if id is None:
            return None
        if IDENTIFIER_RE.fullmatch(id) is None:
            self.error("identifier", f"invalid identifier {id!r}", line, (id,))
        elif id in RESERVED:
            self.error("reserved", f"{id!r} is a reserved word, not an identifier", line, (id,))
        elif id in self.ids:
            where = "" if self.ids[id] is None else f" at line {self.ids[id]}"
            self.error("duplicate-id", f"{id!r} is already used{where}", line, (id,))
        else:
            self.ids[id] = line
            return id
        return None

    def boolean(self, element: Element, name: str) -> bool | None:
        value = element.get(name)
        if value is not None and value not in ("true", "false"):
            self.error("structure", f"{name!r} must be 'true' or 'false'", element.line)
            return None
        return None if value is None else value == "true"

    # ----- Document structure -----

    def read(self, root: Element) -> None:
        if not root.ours or root.name != "sketch":
            self.error(
                "structure", f"the root must be <sketch> in namespace {NAMESPACE}", root.line
            )
            return
        self.check_attrs(root, ("version", "unit-length", "unit-angle"))
        self.read_version(root)
        length = root.get("unit-length") or "mm"
        angle = root.get("unit-angle") or "deg"
        if length not in LENGTH_UNITS:
            self.error("unit", f"unknown length unit {length!r}", root.line)
            length = "mm"
        if angle not in ANGLE_UNITS:
            self.error("unit", f"unknown angle unit {angle!r}", root.line)
            angle = "deg"
        self.units = Units(length, angle)

        position = -1
        for child in root.elements():
            if child.name not in _CONTAINERS:
                self.unknown(child)
                continue
            index = _CONTAINERS.index(child.name)
            if index <= position:
                self.error("structure", f"<{child.name}> is repeated or out of order", child.line)
                continue
            position = index
            self.check_attrs(child, ())
            match child.name:
                case "metadata":
                    self.read_metadata(child)
                case "variables":
                    self.read_variables(child)
                case "geometry":
                    self.read_geometry(child)
                case _:
                    self.read_constraints(child)

    def read_version(self, root: Element) -> None:
        version = self.required(root, "version")
        if version is None:
            return
        self.version = version
        major, _, minor = version.partition(".")
        if not (major.isdigit() and minor.isdigit()):
            self.error("version", f"invalid version {version!r}", root.line)
            return
        found = (int(major), int(minor))
        if found == VERSION:
            return
        if found[0] != VERSION[0] or VERSION[0] == 0 or found < VERSION:
            self.error("version", f"version {version} is not supported (reader: 0.1)", root.line)
        else:
            self.warn("newer-version", f"version {version} is newer than this reader", root.line)

    def read_metadata(self, element: Element) -> None:
        for child in element.elements():
            if child.name not in _METADATA:
                self.unknown(child)
                continue
            self.check_attrs(child, ())
            self.metadata.setdefault(child.name, []).append(child.text.strip())

    def read_variables(self, element: Element) -> None:
        for child in element.elements():
            if child.name == "variable":
                self.read_variable(child)
            else:
                self.unknown(child)

    def read_variable(self, element: Element) -> None:
        self.check_attrs(element, ("id", "type", "value", "min", "max", "description"))
        id = self.register_id(self.required(element, "id"), element.line)
        text = self.required(element, "value")
        type_ = element.get("type") or "number"
        if type_ not in ("number", "length", "angle"):
            self.error("structure", f"unknown variable type {type_!r}", element.line)
            type_ = "number"
        kind = cast(ValueKind, type_)
        formula = None if text is None else self.formula(text, element.line, kind)
        low = self.limit(element, "min", kind)
        high = self.limit(element, "max", kind)
        if id is not None:
            self.variables[id] = _Variable(id, kind, formula, low, high, element.line)

    def formula(self, text: str, line: int | None, kind: ValueKind) -> Node | None:
        try:
            node = parse(text)
        except FormulaError as e:
            self.error("formula", str(e), line)
            return None
        if isinstance(node, Number) and node.unit is not None:
            self.check_unit(node.unit, kind, line)
        return node

    def check_unit(self, unit: str, kind: ValueKind, line: int | None) -> bool:
        if kind != "number" and unit_kind(unit) == kind:
            return True
        expected = "no unit" if kind == "number" else f"a {kind} unit"
        self.error("unit", f"unit {unit!r} where {expected} is expected", line)
        return False

    def limit(self, element: Element, name: str, kind: ValueKind) -> float | None:
        text = element.get(name)
        if text is None:
            return None
        try:
            literal = parse_literal(text)
        except FormulaError as e:
            self.error("structure", f"{name!r}: {e}", element.line)
            return None
        if literal.unit is None:
            return literal.value
        if not self.check_unit(literal.unit, kind, element.line):
            return None
        return self.units.convert(literal.value, literal.unit)

    def read_geometry(self, element: Element) -> None:
        for child in element.elements():
            if child.name in _GEOMETRY_ATTRS:
                self.read_primitive(child)
            else:
                self.unknown(child)

    def read_primitive(self, element: Element) -> None:
        names = _GEOMETRY_ATTRS[element.name]
        self.check_attrs(element, (*names, "id", "construction"))
        id = self.register_id(element.get("id"), element.line)
        values: list[float] = []
        for name in names:
            text = self.required(element, name) or "0"
            if NUMBER_RE.fullmatch(text.strip()) is None:
                message = f"{name!r} must be a plain number, not {text!r}"
                self.error("structure", message, element.line)
                text = "0"
            values.append(float(text))
        geometry: Geometry
        match element.name:
            case "point":
                geometry = Point(*values)
            case "line":
                geometry = Line(*values)
            case "circle":
                geometry = Circle(*values)
            case _:
                cx, cy, r, start, end = values
                geometry = Arc(cx, cy, r, start, end, units=self.units)
        if isinstance(geometry, Circle | Arc) and not geometry.r > 0:
            self.error("structure", f"radius must be positive, not {geometry.r:g}", element.line)
        index = len(self.primitives)
        construction = bool(self.boolean(element, "construction"))
        self.primitives.append(Primitive(index, id, geometry, construction, element.line))
        for child in element.elements():
            self.read_constraint(child, index)

    def read_constraints(self, element: Element) -> None:
        for child in element.elements():
            self.read_constraint(child, None)

    def read_constraint(self, element: Element, parent: int | None) -> None:
        if element.name not in OPERANDS:
            self.unknown(element)
            return
        allowed: tuple[str, ...] = (*OPERANDS[element.name], "id")
        if element.name in _DIMENSIONS:
            allowed = (*allowed, "value", "driving")
        self.check_attrs(element, allowed)
        attrs = {
            name: value
            for (namespace, name), value in element.attrs.items()
            if namespace is None and name in allowed
        }
        raw = _RawConstraint(element.name, attrs, element.line, parent, element)
        self.register_id(raw.id, raw.line)
        if raw.type in _DIMENSIONS:
            self.boolean(element, "driving")
            if raw.driving and "value" not in attrs:
                self.error("structure", f"driving <{raw.type}> needs a 'value'", raw.line)
            elif raw.driving:
                raw.formula = self.formula(attrs["value"], raw.line, _DIMENSIONS[raw.type])
            elif "value" in attrs:
                try:
                    parse_literal(attrs["value"])
                except FormulaError:
                    self.error("structure", "a non-driving 'value' must be a literal", raw.line)
        self.raws.append(raw)

    # ----- Formulas (spec §10.4) -----

    def apply_overrides(self) -> None:
        for name, override in self.overrides.items():
            variable = self.variables.get(name)
            if variable is None:
                self.error("override", f"no variable {name!r} to override", None, (name,))
            elif not isinstance(override, str):
                variable.formula = Number(float(override))
            else:
                try:
                    literal = parse_literal(override)
                except FormulaError as e:
                    self.error("override", f"override of {name!r}: {e}", None, (name,))
                    continue
                if literal.unit is None or self.check_unit(literal.unit, variable.type, None):
                    variable.formula = literal

    def evaluate_all(self) -> tuple[dict[str, float], dict[int, float]]:
        """Values of variables and of identified driving constraints, and of anonymous ones."""
        named = {raw.id: raw for raw in self.raws if raw.id is not None and raw.id in self.ids}
        valued = {id: raw for id, raw in named.items() if raw.type in _DIMENSIONS and raw.driving}
        values: dict[str, float] = {}
        failed: set[str] = set()
        visiting: list[str] = []

        def value_of(id: str, line: int | None) -> float:
            if id in values:
                return values[id]
            if id in failed:
                raise _ReferenceFailedError
            if id in visiting:
                cycle = (*visiting[visiting.index(id) :], id)
                self.error("cycle", f"circular reference: {' -> '.join(cycle)}", line, cycle)
                failed.update(cycle)
                raise _ReferenceFailedError
            if id in self.variables:
                node, where = self.variables[id].formula, self.variables[id].line
            else:
                node, where = valued[id].formula, valued[id].line
            visiting.append(id)
            try:
                if node is None:
                    raise _ReferenceFailedError
                values[id] = evaluate(node, self.units, resolver(where))
            except FormulaError as e:
                self.error("formula", f"{id!r}: {e}", where, (id,))
                failed.add(id)
                raise _ReferenceFailedError from None
            except _ReferenceFailedError:
                failed.add(id)
                raise
            finally:
                visiting.pop()
            return values[id]

        def resolver(line: int | None) -> Callable[[Name], float]:
            def resolve(name: Name) -> float:
                head = name.parts[0]
                if len(name.parts) > 1:
                    message = f"{name}: formulas cannot read solved properties (spec §10.5)"
                    self.error("forbidden-reference", message, line, (head,))
                elif head in named and named[head].type in _DIMENSIONS and not named[head].driving:
                    message = f"{name}: formulas cannot read non-driving constraints (spec §10.5)"
                    self.error("forbidden-reference", message, line, (head,))
                elif head in self.variables or head in valued:
                    return value_of(head, line)
                elif head in self.ids or head in RESERVED:
                    self.error("reference", f"{name!r} has no value", line, (head,))
                else:
                    self.error("reference", f"unknown name {str(name)!r}", line, (head,))
                raise _ReferenceFailedError

            return resolve

        for id, variable in self.variables.items():
            try:
                result = value_of(id, variable.line)
            except _ReferenceFailedError:
                continue
            low, high = variable.low, variable.high
            if (low is not None and result < low) or (high is not None and result > high):
                bounds = (
                    f"[{'' if low is None else f'{low:g}'}, {'' if high is None else f'{high:g}'}]"
                )
                message = f"variable {id!r} = {result:g} is outside {bounds}"
                self.error("limits", message, variable.line, (id,))
        anonymous: dict[int, float] = {}
        for index, raw in enumerate(self.raws):
            if raw.type not in _DIMENSIONS or not raw.driving or raw.formula is None:
                continue
            try:
                if raw.id is not None and raw.id in valued:
                    value_of(raw.id, raw.line)
                else:
                    anonymous[index] = evaluate(raw.formula, self.units, resolver(raw.line))
            except FormulaError as e:
                self.error("formula", str(e), raw.line)
            except _ReferenceFailedError:
                pass
        return values, anonymous

    # ----- Constraints (spec §8, §9) -----

    def resolve(self, text: str, parent: int | None, line: int | None) -> Operand | None:
        parts = text.split(".")
        if not all(IDENTIFIER_RE.fullmatch(part) for part in parts):
            self.error("reference", f"invalid reference {text!r}", line)
            return None
        head, *rest = parts
        if len(rest) > 1:
            self.error("reference", f"{text!r}: an operand cannot be a property", line)
            return None
        target: int | Implicit
        kind: Kind
        if head == "self":
            if parent is None:
                self.error("self", "'self' is only valid in a nested constraint", line)
                return None
            target, kind = parent, self.primitives[parent].kind
        elif head in IMPLICIT:
            target = head
            kind = IMPLICIT[target]
        else:
            found = next((p for p in self.primitives if p.id == head), None)
            if found is None:
                self.error("reference", f"{text!r}: no primitive {head!r}", line, (head,))
                return None
            target, kind = found.index, found.kind
        if not rest:
            return Operand(target, None, kind, text)
        point = rest[0]
        if point not in POINTS[kind]:
            self.error("reference", f"{text!r}: a {kind} has no point {point!r}", line)
            return None
        return Operand(target, point, "point", text)

    def omitted(self, raw: _RawConstraint, given: Mapping[str, str]) -> str | None:
        """The operand a nested constraint omits (``""`` if none), or ``None`` on error."""
        if raw.type in _SINGLE:
            if given:
                self.error("nesting", f"nested <{raw.type}> takes no operands", raw.line)
                return None
            return "of"
        if raw.type in _OF_OR_PAIR and "a" not in given and "b" not in given:
            return "of"
        missing = [name for name in OPERANDS[raw.type] if name != "of" and name not in given]
        if len(missing) > 1:
            names = ", ".join(missing)
            self.error("nesting", f"nested <{raw.type}> omits more than one of {names}", raw.line)
            return None
        return missing[0] if missing else ""

    def build(self, raw: _RawConstraint, value: float | None) -> Constraint | None:
        given = {name: raw.attrs[name] for name in OPERANDS[raw.type] if name in raw.attrs}
        if raw.parent is not None:
            if "of" in given:
                self.error("nesting", f"nested <{raw.type}> must not have 'of'", raw.line)
                return None
            omitted = self.omitted(raw, given)
            if omitted is None:
                return None
            if omitted:
                given[omitted] = "self"
            elif not any(text.split(".")[0] == "self" for text in given.values()):
                message = (
                    f"nested <{raw.type}> must reference its parent: omit an operand or use 'self'"
                )
                self.error("nesting", message, raw.line)
                return None
        operands: dict[str, Operand] = {}
        for name, text in given.items():
            operand = self.resolve(text, raw.parent, raw.line)
            if operand is None:
                return None
            operands[name] = operand
        if not self.check_operands(raw, operands):
            return None
        id = raw.id if raw.id in self.ids else None
        return Constraint(
            raw.type, operands, value, raw.driving, id, raw.line, raw.parent, raw.element
        )

    def check_operands(self, raw: _RawConstraint, ops: Mapping[str, Operand]) -> bool:
        def kinds(*names: str) -> tuple[Kind, ...] | None:
            return tuple(ops[n].kind for n in names) if set(ops) == set(names) else None

        def on_curve_end(op: Operand) -> bool:
            return op.point in ("start", "end")

        pair = kinds("a", "b")
        match raw.type:
            case "coincident" | "distance-x" | "distance-y":
                ok = pair == ("point", "point")
            case "point-on":
                found = kinds("point", "object")
                ok = found is not None and found[0] == "point" and found[1] != "point"
            case "horizontal" | "vertical":
                ok = kinds("of") == ("line",) or pair == ("point", "point")
            case "parallel" | "perpendicular":
                ok = pair == ("line", "line")
            case "tangent":
                if pair == ("point", "point"):
                    ok = on_curve_end(ops["a"]) and on_curve_end(ops["b"])
                else:
                    ok = pair is not None and "point" not in pair and pair != ("line", "line")
            case "equal":
                ok = pair == ("line", "line") or (
                    pair is not None and set(pair) <= {"circle", "arc"}
                )
            case "symmetric":
                found = kinds("a", "b", "about")
                ok = found in (("point", "point", "point"), ("point", "point", "line"))
            case "block":
                ok = kinds("of") is not None and isinstance(ops["of"].target, int)
                ok = ok and ops["of"].point is None
            case "distance":
                ok = kinds("of") == ("line",) or pair in (
                    ("point", "point"),
                    ("point", "line"),
                    ("line", "point"),
                )
            case "radius" | "diameter":
                ok = kinds("of") in (("circle",), ("arc",))
            case _:
                ok = kinds("of") == ("arc",) or pair == ("line", "line")
        if not ok:
            written = ", ".join(f"{name}={op.text!r} ({op.kind})" for name, op in ops.items())
            message = f"<{raw.type}> does not take these operands: {written or 'none'}"
            self.error("operand", message, raw.line)
        return ok


def compile_document(document: Document, overrides: Overrides | None = None) -> Sketch:
    """Validate a parsed document and evaluate its formulas into a :class:`Sketch`.

    ``overrides`` replaces variable values with a number (in the document unit) or a literal
    such as ``"5cm"``. Raises :class:`CpskLoadError` listing every load error found; warnings
    are in :attr:`Sketch.warnings`.
    """
    reader = _Reader(dict(overrides or {}))
    reader.read(document.root)
    reader.apply_overrides()
    values, anonymous = reader.evaluate_all()
    constraints: list[Constraint] = []
    for index, raw in enumerate(reader.raws):
        value = anonymous.get(index, values.get(raw.id or ""))
        if raw.type in _DIMENSIONS and raw.driving and value is None:
            continue
        constraint = reader.build(raw, value)
        if constraint is not None:
            constraints.append(constraint)
    errors = [d for d in reader.diagnostics if d.severity == Severity.ERROR]
    if errors:
        raise CpskLoadError(errors)
    return Sketch(
        version=reader.version,
        units=reader.units,
        metadata={key: tuple(items) for key, items in reader.metadata.items()},
        variables={id: values[id] for id in reader.variables},
        primitives=tuple(reader.primitives),
        constraints=tuple(constraints),
        warnings=tuple(reader.diagnostics),
        document=document,
    )


def loads(text: str | bytes, overrides: Overrides | None = None) -> Sketch:
    """Parse and compile a CPSK document from a string (see :func:`compile_document`)."""
    return compile_document(parse_document(text), overrides)


def load(path: str | Path, overrides: Overrides | None = None) -> Sketch:
    """Parse and compile a CPSK document file (see :func:`compile_document`)."""
    return loads(Path(path).read_bytes(), overrides)
