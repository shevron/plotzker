"""Preview a part or assembly in the PythonSCAD app.

Open this file in PythonSCAD, set ``NAME`` to a key of ``PRINTABLE_PARTS`` or
``ASSEMBLIES`` (see ``python -m plotter_cad render --help``), and render.
"""

import sys
from pathlib import Path

try:
    _ROOT = Path(__file__).resolve().parent
except NameError:  # some PythonSCAD versions run scripts without __file__
    _ROOT = Path.cwd()
sys.path.insert(0, str(_ROOT / "src"))

from pythonscad import show

from plotter_cad.assemblies import ASSEMBLIES
from plotter_cad.parts import PRINTABLE_PARTS

NAME = "skeleton"

show({**PRINTABLE_PARTS, **ASSEMBLIES}[NAME]())
