"""FreeCAD expressions ↔ CPSK formulas (plugin plan §4.3).

FreeCAD and CPSK 0.1 differ in precedence: in FreeCAD unary minus binds tighter than ``^`` and
``^`` is left-associative (``-2^2`` is 4, ``2^3^2`` is 64); in CPSK ``^`` binds tighter and is
right-associative (spec §10.2). The translator parses with FreeCAD's rules and writes the CPSK
text with the parentheses CPSK needs. Number literals keep their text; units are written as
CPSK suffixes (``2.5 cm`` → ``2.5cm``, ``30 °`` → ``30deg``).

References are resolved by a callback that turns a FreeCAD object path into a CPSK identifier.
Anything CPSK 0.1 cannot express raises :class:`UnsupportedExpressionError`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from cpsk_core import formula as cpsk_formula
from cpsk_core.document import format_number

UNITS = {"mm": "mm", "cm": "cm", "m": "m", "in": "in", "deg": "deg", "°": "deg", "rad": "rad"}
"""FreeCAD unit → CPSK unit."""

FUNCTIONS = frozenset(
    {"abs", "sqrt", "min", "max", "sin", "cos", "tan", "asin", "acos", "atan", "atan2"}
)
CONSTANTS = frozenset({"pi"})

_TOKEN_RE = re.compile(
    r"""\s*(?:
      (?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)
    | (?P<label><<[^>]*>>)
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<degree>°)
    | (?P<op>[-+*/^(),;.])
    )""",
    re.VERBOSE,
)


class UnsupportedExpressionError(Exception):
    """The expression has no CPSK 0.1 equivalent; the message says why."""


@dataclass(frozen=True)
class Path:
    """A FreeCAD object path such as ``Vars.width``, ``<<My vars>>.width``, ``.Constraints.w``.

    ``parts[0]`` is the object: a name, a label (``label`` is true) or ``""`` for the object that
    owns the expression (a leading ``.``). A path of one part (``width``) is a property of the
    owning object: ``parts == ("", "width")``.
    """

    parts: tuple[str, ...]
    label: bool = False

    def __str__(self) -> str:
        head = f"<<{self.parts[0]}>>" if self.label else self.parts[0]
        return ".".join((head, *self.parts[1:]))


Resolver: TypeAlias = Callable[[Path], str]
"""Turns a reference into a CPSK identifier; raises :class:`UnsupportedExpressionError`."""


def translate(expression: str, resolve: Resolver) -> str:
    """The CPSK formula for a FreeCAD expression."""
    parser = _Parser(_tokens(expression), resolve, expression)
    node = parser.sum()
    if parser.peek() is not None:
        raise UnsupportedExpressionError(f"unexpected {parser.peek()!r} in {expression!r}")
    return _write(node)[0]


# ----- Tokens -----

_Token: TypeAlias = tuple[str, str]  # (kind, text)


def _tokens(expression: str) -> list[_Token]:
    tokens: list[_Token] = []
    position = 0
    rest = expression.rstrip()
    while position < len(rest):
        match = _TOKEN_RE.match(rest, position)
        if match is None or match.lastgroup is None:
            character = rest[position:].lstrip()[:1]
            raise UnsupportedExpressionError(f"{character!r} is not supported (in {expression!r})")
        tokens.append((match.lastgroup, match.group(match.lastgroup)))
        position = match.end()
    return tokens


# ----- Parsing, with FreeCAD's precedence -----

_Node: TypeAlias = tuple[object, ...]
# ("number", text) · ("ref", identifier) · ("call", name, [args]) · ("unary", op, x)
# · ("binary", op, left, right)


class _Parser:
    def __init__(self, tokens: list[_Token], resolve: Resolver, source: str) -> None:
        self.tokens = tokens
        self.index = 0
        self.resolve = resolve
        self.source = source

    def peek(self) -> str | None:
        return self.tokens[self.index][1] if self.index < len(self.tokens) else None

    def kind(self) -> str | None:
        return self.tokens[self.index][0] if self.index < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        if self.index >= len(self.tokens):
            raise UnsupportedExpressionError(f"incomplete expression {self.source!r}")
        text = self.tokens[self.index][1]
        if expected is not None and text != expected:
            raise UnsupportedExpressionError(
                f"expected {expected!r}, found {text!r} in {self.source!r}"
            )
        self.index += 1
        return text

    def sum(self) -> _Node:
        node = self.product()
        while self.peek() in ("+", "-"):
            node = ("binary", self.take(), node, self.product())
        return node

    def product(self) -> _Node:
        node = self.power()
        while self.peek() in ("*", "/"):
            node = ("binary", self.take(), node, self.power())
        return node

    def power(self) -> _Node:  # left-associative, operands are unary (FreeCAD)
        node = self.unary()
        while self.peek() == "^":
            node = ("binary", self.take(), node, self.unary())
        return node

    def unary(self) -> _Node:
        if self.peek() in ("+", "-"):
            return "unary", self.take(), self.unary()
        return self.primary()

    def primary(self) -> _Node:
        kind, text = self.kind(), self.peek()
        if text is None:
            raise UnsupportedExpressionError(f"incomplete expression {self.source!r}")
        if kind == "number":
            return self.number()
        if text == "(":
            self.take()
            node = self.sum()
            self.take(")")
            return node
        if (
            kind == "name"
            and self.index + 1 < len(self.tokens)
            and self.tokens[self.index + 1][1] == "("
        ):
            return self.call()
        if kind == "name" and text in CONSTANTS:
            self.take()
            return "ref", text
        if kind in ("name", "label") or text == ".":
            return self.reference()
        raise UnsupportedExpressionError(f"unexpected {text!r} in {self.source!r}")

    def number(self) -> _Node:
        text = self.take()
        if self.kind() in ("name", "degree"):
            unit = self.peek() or ""
            if unit not in UNITS:
                raise UnsupportedExpressionError(f"unit {unit!r} is not supported")
            self.take()
            text += UNITS[unit]
        return "number", text

    def call(self) -> _Node:
        name = self.take()
        if name not in FUNCTIONS:
            raise UnsupportedExpressionError(f"function {name!r} is not supported")
        self.take("(")
        args = [self.sum()]
        while self.peek() in (",", ";"):  # FreeCAD stores ";" between arguments
            self.take()
            args.append(self.sum())
        self.take(")")
        return "call", name, args

    def reference(self) -> _Node:
        label = self.kind() == "label"
        if self.peek() == ".":
            parts = [""]
        else:
            head = self.take()
            parts = [head[2:-2] if label else head]
        while self.peek() == ".":
            self.take()
            if self.kind() != "name":
                raise UnsupportedExpressionError(f"unsupported reference in {self.source!r}")
            parts.append(self.take())
        if len(parts) == 1:
            parts.insert(0, "")
        return "ref", self.resolve(Path(tuple(parts), label))


# ----- Writing, with CPSK's precedence -----

# Levels: 1 sum, 2 product, 3 unary, 4 power, 5 primary.


def _write(node: _Node) -> tuple[str, int]:
    kind = node[0]
    if kind in ("number", "ref"):
        return str(node[1]), 5
    if kind == "call":
        args = node[2]
        assert isinstance(args, list)
        return f"{node[1]}({', '.join(_write(a)[0] for a in args)})", 5
    if kind == "unary":
        return f"{node[1]}{_wrap(node[2], 3)}", 3
    op, left, right = node[1], node[2], node[3]
    if op == "^":
        return f"{_wrap(left, 5)}^{_wrap(right, 3)}", 4
    if op in ("*", "/"):
        return f"{_wrap(left, 2)} {op} {_wrap(right, 3)}", 2
    return f"{_wrap(left, 1)} {op} {_wrap(right, 2)}", 1


def _wrap(node: object, level: int) -> str:
    assert isinstance(node, tuple)
    text, own = _write(node)
    return text if own >= level else f"({text})"


# ----- CPSK → FreeCAD -----

FREECAD_UNITS = {"mm": "mm", "cm": "cm", "m": "m", "in": "in", "deg": "°", "rad": "rad"}
"""CPSK unit → FreeCAD unit."""


Dimension: TypeAlias = str | None
"""``"length"``, ``"angle"``, ``"other"`` (an area, a mix) or ``None`` (dimensionless)."""

_DIMENSIONED = {"length": "mm", "angle": "°"}
"""Dimensions FreeCAD checks in sums, and the unit a CPSK mm/deg document means for them."""


def to_freecad(
    formula: str,
    resolve: Callable[[str], str],
    dimension: Callable[[str], Dimension] = lambda name: None,
) -> str:
    """The FreeCAD expression for a CPSK formula in a millimetre and degree document.

    ``resolve`` turns an identifier into a FreeCAD reference (e.g. ``width`` → ``Vars.width``),
    ``dimension`` says what it measures. Written with FreeCAD's precedence (``-2^2`` →
    ``-(2 ^ 2)``, ``2^3^2`` → ``2 ^ (3 ^ 2)``). FreeCAD checks units in ``+``, ``-``, ``min``
    and ``max``, where a CPSK document's unitless number means millimetres or degrees: there
    such a number gets its unit (``s - 6`` → ``s - 6 mm``), and a unitless subexpression is
    multiplied by ``1 mm`` or ``1 °``.
    """
    return _Writer(resolve, dimension).write(cpsk_formula.parse(formula))[0]


# FreeCAD levels: 1 sum, 2 product, 3 power (left-associative), 4 unary, 5 primary.


class _Writer:
    def __init__(self, resolve: Callable[[str], str], dimension: Callable[[str], Dimension]):
        self.resolve = resolve
        self.dimension = dimension

    def write(self, node: cpsk_formula.Node) -> tuple[str, int, Dimension]:
        match node:
            case cpsk_formula.Number(value=value, unit=None) if value == math.pi:
                return "pi", 5, None  # the parser folds the constant into a number
            case cpsk_formula.Number(value=value, unit=None):
                return format_number(value), 5, None
            case cpsk_formula.Number(value=value, unit=str(unit)):
                kind = cpsk_formula.unit_kind(unit)
                return f"{format_number(value)} {FREECAD_UNITS[unit]}", 5, kind
            case cpsk_formula.Name(parts=parts):
                name = ".".join(parts)
                if name in CONSTANTS:
                    return name, 5, None
                return self.resolve(name), 5, self.dimension(name)
            case cpsk_formula.Call(function=function, args=args):
                return self.call(function, args)
            case cpsk_formula.Unary(op=op, operand=operand):
                text, level, dim = self.write(operand)
                return f"{op}{_paren(text, level, 4)}", 4, dim
            case cpsk_formula.Binary(op="^", left=left, right=right):
                (lt, ll, ld), (rt, rl, _) = self.write(left), self.write(right)
                return (
                    f"{_paren(lt, ll, 3)} ^ {_paren(rt, rl, 4)}",
                    3,
                    None if ld is None else "other",
                )
            case cpsk_formula.Binary(op=op, left=left, right=right) if op in ("*", "/"):
                (lt, ll, ld), (rt, rl, rd) = self.write(left), self.write(right)
                if op == "*":
                    dim = rd if ld is None else ld if rd is None else "other"
                else:
                    dim = ld if rd is None else None if ld == rd else "other"
                return f"{_paren(lt, ll, 2)} {op} {_paren(rt, rl, 3)}", 2, dim
            case cpsk_formula.Binary(op=op, left=left, right=right):
                (lt, ll, ld), (rt, rl, rd) = self.matched([left, right])
                return f"{_paren(lt, ll, 1)} {op} {_paren(rt, rl, 2)}", 1, ld or rd
        raise AssertionError(node)

    def call(
        self, function: str, args: tuple[cpsk_formula.Node, ...]
    ) -> tuple[str, int, Dimension]:
        if function in ("min", "max", "abs"):
            written = self.matched(list(args))
            dim = next((d for _, _, d in written if d is not None), None)
        else:
            written = [self.write(a) for a in args]
            dim = {"sin": None, "cos": None, "tan": None, "sqrt": "other"}.get(function, "angle")
            if function == "sqrt" and written[0][2] is None:
                dim = None
        return f"{function}({'; '.join(text for text, _, _ in written)})", 5, dim

    def matched(self, nodes: list[cpsk_formula.Node]) -> list[tuple[str, int, Dimension]]:
        """Operands that FreeCAD adds or compares: unitless ones get the others' unit."""
        written = [self.write(n) for n in nodes]
        dims = {d for _, _, d in written} - {None}
        if len(dims) != 1 or (dim := dims.pop()) not in _DIMENSIONED:
            return written
        unit = _DIMENSIONED[dim]
        result: list[tuple[str, int, Dimension]] = []
        for node, (text, level, own) in zip(nodes, written, strict=True):
            if own is not None:
                result.append((text, level, own))
            elif isinstance(node, cpsk_formula.Number) and text != "pi":
                result.append((f"{text} {unit}", 5, dim))
            elif isinstance(node, cpsk_formula.Unary) and isinstance(
                node.operand, cpsk_formula.Number
            ):
                result.append((f"{text} {unit}", 4, dim))
            else:
                result.append((f"{_paren(text, level, 2)} * 1 {unit}", 2, dim))
        return result


def _paren(text: str, own: int, level: int) -> str:
    return text if own >= level else f"({text})"


def is_plain_number(formula: str) -> bool:
    """Whether a formula is a number without a unit, optionally negated (no expression needed)."""
    node = cpsk_formula.parse(formula)
    if isinstance(node, cpsk_formula.Unary):
        node = node.operand
    return isinstance(node, cpsk_formula.Number) and node.unit is None
