"""CPSK formulas: units, parsing and evaluation (spec §4, §10)."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal, TypeAlias

UnitKind: TypeAlias = Literal["length", "angle"]

LENGTH_UNITS: dict[str, float] = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}
"""Length units and their size in millimeters."""

ANGLE_UNITS: dict[str, float] = {"deg": math.pi / 180, "rad": 1.0}
"""Angle units and their size in radians."""

UNITS = frozenset(LENGTH_UNITS) | frozenset(ANGLE_UNITS)
CONSTANTS: dict[str, float] = {"pi": math.pi}
FUNCTIONS = frozenset(
    {"abs", "sqrt", "min", "max", "sin", "cos", "tan", "asin", "acos", "atan", "atan2"}
)

_UNSIGNED = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_NUMBER = rf"[+-]?{_UNSIGNED}"
_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_UNIT = "|".join(sorted(UNITS, key=len, reverse=True))

NUMBER_RE = re.compile(_NUMBER)
"""A plain number (spec §3.3), e.g. a stored coordinate."""
LITERAL_RE = re.compile(rf"(?P<number>{_NUMBER})\s*(?P<unit>{_UNIT})?")
"""A number with an optional unit (spec §3.4)."""
IDENTIFIER_RE = re.compile(_IDENTIFIER)
"""An identifier (spec §3.1)."""

# In formulas a sign is an operator, so numbers are unsigned tokens.
_TOKEN_RE = re.compile(
    rf"\s*(?:(?P<number>{_UNSIGNED})|(?P<name>{_IDENTIFIER})|(?P<op>[-+*/^(),.]))"
)


class FormulaError(ValueError):
    """A formula is malformed or cannot be evaluated."""


def unit_kind(unit: str) -> UnitKind:
    """Whether a unit measures lengths or angles."""
    return "length" if unit in LENGTH_UNITS else "angle"


@dataclass(frozen=True)
class Units:
    """A document's length and angle units, and conversions to them."""

    length: str = "mm"
    angle: str = "deg"

    def convert(self, value: float, unit: str) -> float:
        """``value`` in ``unit``, expressed in the document unit of the same kind."""
        if unit in LENGTH_UNITS:
            return value * LENGTH_UNITS[unit] / LENGTH_UNITS[self.length]
        return value * ANGLE_UNITS[unit] / ANGLE_UNITS[self.angle]

    def to_radians(self, angle: float) -> float:
        """An angle in the document unit, in radians."""
        return angle * ANGLE_UNITS[self.angle]

    def from_radians(self, angle: float) -> float:
        """An angle in radians, in the document unit."""
        return angle / ANGLE_UNITS[self.angle]

    def to_mm(self, length: float) -> float:
        """A length in the document unit, in millimeters."""
        return length * LENGTH_UNITS[self.length]


# ----- Syntax tree -----


@dataclass(frozen=True)
class Number:
    """A literal, optionally with a unit."""

    value: float
    unit: str | None = None


@dataclass(frozen=True)
class Name:
    """A reference: an identifier, optionally followed by ``.part`` segments."""

    parts: tuple[str, ...]

    def __str__(self) -> str:
        return ".".join(self.parts)


@dataclass(frozen=True)
class Unary:
    """``+x`` or ``-x``."""

    op: str
    operand: Node


@dataclass(frozen=True)
class Binary:
    """``x op y`` for ``+ - * / ^``."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Call:
    """A function call."""

    function: str
    args: tuple[Node, ...]


Node: TypeAlias = Number | Name | Unary | Binary | Call


def parse_literal(text: str) -> Number:
    """Parse a literal with an optional unit (spec §3.4), e.g. ``2.5 cm``."""
    match = LITERAL_RE.fullmatch(text.strip())
    if match is None:
        raise FormulaError(f"not a literal: {text!r}")
    return Number(float(match["number"]), match["unit"])


def parse(text: str) -> Node:
    """Parse a formula (spec §10.2)."""
    return _Parser(text).parse()


def names(node: Node) -> Iterator[Name]:
    """The references in a formula."""
    match node:
        case Name():
            yield node
        case Unary(operand=operand):
            yield from names(operand)
        case Binary(left=left, right=right):
            yield from names(left)
            yield from names(right)
        case Call(args=args):
            for arg in args:
                yield from names(arg)


def evaluate(node: Node, units: Units, resolve: Callable[[Name], float]) -> float:
    """Evaluate a formula; literals with units are converted to the document units."""
    try:
        result = _evaluate(node, units, resolve)
    except ZeroDivisionError:
        raise FormulaError("division by zero") from None
    except OverflowError:
        raise FormulaError("result too large") from None
    if not math.isfinite(result):
        raise FormulaError("result is not a finite number")
    return result


def _evaluate(node: Node, units: Units, resolve: Callable[[Name], float]) -> float:
    match node:
        case Number(value=value, unit=None):
            return value
        case Number(value=value, unit=str(unit)):
            return units.convert(value, unit)
        case Name():
            return resolve(node)
        case Unary(op=op, operand=operand):
            value = _evaluate(operand, units, resolve)
            return -value if op == "-" else value
        case Binary(op=op, left=left, right=right):
            a = _evaluate(left, units, resolve)
            b = _evaluate(right, units, resolve)
            match op:
                case "+":
                    return a + b
                case "-":
                    return a - b
                case "*":
                    return a * b
                case "/":
                    return a / b
                case _:
                    return _power(a, b)
        case Call(function=function, args=args):
            values = [_evaluate(arg, units, resolve) for arg in args]
            return _call(function, values, units)
    raise AssertionError(node)


def _power(base: float, exponent: float) -> float:
    try:
        return math.pow(base, exponent)
    except ValueError:
        raise FormulaError(f"{base:g} ^ {exponent:g} is undefined") from None


def _call(function: str, args: list[float], units: Units) -> float:
    try:
        match function:
            case "abs":
                return abs(args[0])
            case "sqrt":
                return math.sqrt(args[0])
            case "min":
                return min(args)
            case "max":
                return max(args)
            case "sin":
                return math.sin(units.to_radians(args[0]))
            case "cos":
                return math.cos(units.to_radians(args[0]))
            case "tan":
                return math.tan(units.to_radians(args[0]))
            case "asin":
                return units.from_radians(math.asin(args[0]))
            case "acos":
                return units.from_radians(math.acos(args[0]))
            case "atan":
                return units.from_radians(math.atan(args[0]))
            case _:
                return units.from_radians(math.atan2(args[0], args[1]))
    except ValueError:
        raise FormulaError(f"{function}() argument out of its domain") from None


_ARITY: dict[str, tuple[int, int | None]] = {
    "min": (2, None),
    "max": (2, None),
    "atan2": (2, 2),
}


class _Parser:
    """Recursive-descent parser for the grammar in spec §10.2."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = self._tokenize(text)
        self.pos = 0

    @staticmethod
    def _tokenize(text: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        pos = 0
        while pos < len(text):
            if text[pos:].strip() == "":
                break
            match = _TOKEN_RE.match(text, pos)
            if match is None:
                bad = text[pos:].lstrip()[:1]
                raise FormulaError(f"unexpected character {bad!r} in {text!r}")
            kind = match.lastgroup
            assert kind is not None
            tokens.append((kind, match[kind]))
            pos = match.end()
        return tokens

    def parse(self) -> Node:
        if not self.tokens:
            raise FormulaError("empty formula")
        node = self._sum()
        if self.pos < len(self.tokens):
            raise FormulaError(f"unexpected {self.tokens[self.pos][1]!r} in {self.text!r}")
        return node

    def _peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _take(self, *ops: str) -> str | None:
        token = self._peek()
        if token is not None and token[0] == "op" and token[1] in ops:
            self.pos += 1
            return token[1]
        return None

    def _expect(self, op: str) -> None:
        if self._take(op) is None:
            raise FormulaError(f"expected {op!r} in {self.text!r}")

    def _sum(self) -> Node:
        node = self._product()
        while (op := self._take("+", "-")) is not None:
            node = Binary(op, node, self._product())
        return node

    def _product(self) -> Node:
        node = self._unary()
        while (op := self._take("*", "/")) is not None:
            node = Binary(op, node, self._unary())
        return node

    def _unary(self) -> Node:
        if (op := self._take("+", "-")) is not None:
            return Unary(op, self._unary())
        return self._power()

    def _power(self) -> Node:
        node = self._primary()
        if self._take("^") is not None:
            node = Binary("^", node, self._unary())
        return node

    def _primary(self) -> Node:
        token = self._peek()
        if token is None:
            raise FormulaError(f"unexpected end of {self.text!r}")
        kind, text = token
        if kind == "number":
            self.pos += 1
            unit = self._peek()
            if unit is not None and unit[0] == "name" and unit[1] in UNITS:
                self.pos += 1
                return Number(float(text), unit[1])
            return Number(float(text))
        if kind == "name":
            self.pos += 1
            if text in UNITS:
                raise FormulaError(f"unit {text!r} must follow a number in {self.text!r}")
            if text in FUNCTIONS:
                return self._call(text)
            if text in CONSTANTS:
                return Number(CONSTANTS[text])
            parts = [text]
            while self._take(".") is not None:
                part = self._peek()
                if part is None or part[0] != "name":
                    raise FormulaError(f"expected a name after '.' in {self.text!r}")
                parts.append(part[1])
                self.pos += 1
            return Name(tuple(parts))
        if self._take("(") is not None:
            node = self._sum()
            self._expect(")")
            return node
        raise FormulaError(f"unexpected {text!r} in {self.text!r}")

    def _call(self, function: str) -> Node:
        self._expect("(")
        args = [self._sum()]
        while self._take(",") is not None:
            args.append(self._sum())
        self._expect(")")
        low, high = _ARITY.get(function, (1, 1))
        if len(args) < low or (high is not None and len(args) > high):
            raise FormulaError(f"wrong number of arguments to {function}() in {self.text!r}")
        return Call(function, tuple(args))
