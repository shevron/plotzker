"""CPSK parametric sketches in cadder: the core format (``cpsk_core``), solving and SVG export.

The format is specified in ``cadder/docs/cpsk/spec-0.1.md``. Typical use::

    from cadder import cpsk

    sketch = cpsk.load("plate.cpsk", overrides={"width": 60})
    solved = cpsk.solve(sketch)
    svg = cpsk.to_svg(solved)

Everything ``cpsk_core`` exports is available here too.
"""

from cadder.cpsk.solver import SolvedSketch, solve
from cadder.cpsk.svg import svg_origin, to_svg
from cpsk_core import *  # noqa: F403 - republishes cpsk_core's public API
from cpsk_core import __all__ as _core_all

__all__ = [*_core_all, "SolvedSketch", "solve", "svg_origin", "to_svg"]
