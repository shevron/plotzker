"""CPSK core: the constraint-based parametric sketch format without a solver.

Pure standard library, Python 3.11 or newer, so that FreeCAD's Python can use it too. It parses
and writes documents losslessly (:mod:`cpsk_core.document`) and compiles them into validated
sketches with evaluated formulas (:mod:`cpsk_core.reader`). Solving and SVG export are in
``cadder.cpsk``. The format is specified in ``cadder/docs/cpsk/spec-0.1.md``.
"""

from cpsk_core.canonical import nest_constraints
from cpsk_core.document import NAMESPACE, Comment, Document, Element, element, format_number
from cpsk_core.errors import (
    CpskError,
    CpskExportError,
    CpskLoadError,
    CpskSolveError,
    CpskWarning,
    Diagnostic,
    Severity,
    Stage,
)
from cpsk_core.model import Arc, Circle, Constraint, Line, Point, Primitive, Sketch
from cpsk_core.reader import OPERANDS, RESERVED, compile_document, load, loads

__all__ = [
    "NAMESPACE",
    "OPERANDS",
    "RESERVED",
    "Arc",
    "Circle",
    "Comment",
    "Constraint",
    "CpskError",
    "CpskExportError",
    "CpskLoadError",
    "CpskSolveError",
    "CpskWarning",
    "Diagnostic",
    "Document",
    "Element",
    "Line",
    "Point",
    "Primitive",
    "Severity",
    "Sketch",
    "Stage",
    "compile_document",
    "element",
    "format_number",
    "load",
    "loads",
    "nest_constraints",
]
