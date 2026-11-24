"""Rendering settings and small geometry helpers for parts.

Units: millimeters and degrees throughout.
"""

import hashlib
import math
import os
import tempfile
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pythonscad import circle, cube, linear_extrude, osimport, square

if TYPE_CHECKING:
    from pythonscad import Solid

#: Facets for round features (OpenSCAD ``$fn``) in rendered output. ``CADDER_FN`` lowers it
#: for the FEM meshes (64-facet holes make the mesher choke).
FN = int(os.environ.get("CADDER_FN", "64"))
#: Facets for holes. Kept separate so holes can be tuned independently.
FN_HOLE = FN
#: Overlap used to keep boolean operations clean (no coplanar faces).
EPS = 0.01


def cos_deg(angle: float) -> float:
    """Cosine of an angle given in degrees (OpenSCAD's ``cos``)."""
    return math.cos(math.radians(angle))


def vadd(a: Sequence[float], b: Sequence[float]) -> tuple[float, ...]:
    """Element-wise sum of two vectors."""
    return tuple(x + y for x, y in zip(a, b, strict=True))


def box(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> Solid:
    """Axis-aligned box between two corners ``(x0, y0, z0)`` and ``(x1, y1, z1)``."""
    return cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def load_sketch(
    path: str | Path,
    fn: int | None = None,
    *,
    params: Mapping[str, float | str] | None = None,
    strict: bool = False,
) -> Solid:
    """Load a 2D sketch from an SVG or CPSK file; returns a 2D object ready to extrude.

    SVG conventions: 1 SVG user unit = 1 mm (``width``/``height`` in mm with a
    ``viewBox`` in the same numbers). The viewBox's bottom-left corner becomes the
    origin and the sketch keeps the orientation it is drawn in (SVG y is flipped on
    import). Every shape is imported as a filled area: strokes and colors are
    ignored, and separate shapes are unioned. Holes are sub-paths of the same
    ``<path>`` with ``fill-rule="evenodd"``.

    A ``.cpsk`` file (a parametric sketch, ``cadder/docs/cpsk/spec-0.1.md``) is solved and
    loaded in its own coordinates (sketch origin at the origin, in mm). ``params`` overrides
    its variables (a number in the document unit, or a literal such as ``"5cm"``). Its closed
    loops are filled, inner loops are holes; geometry that is not closed is an error
    (:class:`cadder.cpsk.CpskExportError`). Load and solve warnings (e.g. an under-constrained
    sketch) are issued as :class:`cadder.cpsk.CpskWarning`; with ``strict``, solve warnings are
    errors (:class:`cadder.cpsk.CpskSolveError`).

    A sketch normally lives next to the module that uses it:
    ``load_sketch(Path(__file__).with_name("vslot_2020.svg"))``. ``fn`` sets the
    facet count of curves (default: the importer's own, about 28 per circle).
    """
    path = Path(path).resolve()  # the importer needs an absolute path
    if not path.is_file():
        raise FileNotFoundError(f"Sketch not found: {path}")
    offset = (0.0, 0.0)
    if path.suffix.lower() == ".cpsk":
        path, offset = _solve_cpsk(path, params or {}, strict)
    elif params:
        raise ValueError(f"params are only valid for .cpsk sketches, not {path.name}")
    sketch = osimport(str(path)) if fn is None else osimport(str(path), fn=fn)
    return sketch.translate([*offset, 0]) if offset != (0.0, 0.0) else sketch


def _solve_cpsk(
    path: Path, params: Mapping[str, float | str], strict: bool
) -> tuple[Path, tuple[float, float]]:
    """Solve a CPSK sketch into a cached SVG file; returns it and the shift to undo on import.

    The importer reads its file only when the geometry is evaluated, so the SVG must outlive
    this call: it is kept in the system temporary folder under a hash of its content.
    """
    # Imported here, not at module level: the solver loads a native extension (planegcs) that
    # the signed PythonSCAD app refuses to load, so importing it on every use of this module
    # would break rendering of all parts, not only those built from a .cpsk sketch.
    from cadder import cpsk

    sketch = cpsk.load(path, params)
    solved = cpsk.solve(sketch, strict=strict)
    for diagnostic in (*sketch.warnings, *solved.warnings):
        warnings.warn(f"{path.name}: {diagnostic}", cpsk.CpskWarning, stacklevel=3)
    svg = cpsk.to_svg(solved)
    cache = Path(tempfile.gettempdir()) / "cadder-cpsk"
    cache.mkdir(exist_ok=True)
    target = cache / f"{hashlib.sha256(svg.encode()).hexdigest()[:24]}.svg"
    if not target.exists():
        partial = target.with_suffix(f".{os.getpid()}.tmp")
        partial.write_text(svg)
        partial.replace(target)
    return target, cpsk.svg_origin(solved)


def teardrop(d: float) -> Solid:
    """2D horizontal-hole profile printable without support.

    A circle with a 45° point toward +Y, in the XY plane. Rotate it into place.
    """
    return circle(d=d, fn=FN_HOLE) | square([d / 2, d / 2]).rotate([0, 0, 45])


def teardrop_x(d: float, length: float) -> Solid:
    """Teardrop hole along the X axis (point up, +Z), centered on the origin."""
    return linear_extrude(teardrop(d), height=length, center=True).rotate([90, 0, 90])


def teardrop_y(d: float, length: float) -> Solid:
    """Teardrop hole along the Y axis (point up, +Z), centered on the origin."""
    return linear_extrude(teardrop(d), height=length, center=True).rotate([90, 0, 0])


def lever_couple(arm: Sequence[float], force: Sequence[float]) -> tuple[float, float, float]:
    """The couple (N·mm) of moving a force by ``arm`` (mm): arm × force."""
    return (
        arm[1] * force[2] - arm[2] * force[1],
        arm[2] * force[0] - arm[0] * force[2],
        arm[0] * force[1] - arm[1] * force[0],
    )
