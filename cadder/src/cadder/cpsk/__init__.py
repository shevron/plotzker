"""CPSK, the constraint-based parametric sketch format: reader, solver and SVG export.

The format is specified in ``cadder/docs/cpsk/spec-0.1.md``. Typical use::

    from cadder import cpsk

    sketch = cpsk.load("plate.cpsk", overrides={"width": 60})
    solved = sketch.solve()
    svg = cpsk.to_svg(solved)
"""

from cadder.cpsk.errors import (
    CpskError,
    CpskExportError,
    CpskLoadError,
    CpskSolveError,
    CpskWarning,
    Diagnostic,
    Severity,
    Stage,
)
from cadder.cpsk.model import Arc, Circle, Constraint, Line, Point, Primitive, Sketch
from cadder.cpsk.reader import NAMESPACE, RESERVED, load, loads
from cadder.cpsk.solver import SolvedSketch, solve
from cadder.cpsk.svg import svg_origin, to_svg

__all__ = [
    "NAMESPACE",
    "RESERVED",
    "Arc",
    "Circle",
    "Constraint",
    "CpskError",
    "CpskExportError",
    "CpskLoadError",
    "CpskSolveError",
    "CpskWarning",
    "Diagnostic",
    "Line",
    "Point",
    "Primitive",
    "Severity",
    "Sketch",
    "SolvedSketch",
    "Stage",
    "load",
    "loads",
    "solve",
    "svg_origin",
    "to_svg",
]
