"""CPSK import and export for FreeCAD's Sketcher (cadder/docs/cpsk/freecad-plugin-plan.md).

Runs in FreeCAD's Python (3.11). The modules do not import FreeCAD themselves (except where they
create objects): they read sketches through their Python attributes.

``cpsk_core`` must be importable. When the addon is linked into FreeCAD's ``Mod`` folder from
the cadder repository (``make freecad-addon``), it is found in the repository's ``src``.
"""

import sys
from pathlib import Path

try:
    import cpsk_core  # noqa: F401
except ImportError:  # linked from the repository: cadder/src holds cpsk_core
    _SRC = Path(__file__).resolve().parents[3] / "src"
    if (_SRC / "cpsk_core").is_dir():
        sys.path.append(str(_SRC))

from cpsk_core import CpskError, Diagnostic
from cpsk_freecad.export_sketch import FREECAD_NAMESPACE, export_sketch, to_document
from cpsk_freecad.import_sketch import from_document, import_sketch

__all__ = [
    "FREECAD_NAMESPACE",
    "CpskError",
    "Diagnostic",
    "export_sketch",
    "from_document",
    "import_sketch",
    "to_document",
]
