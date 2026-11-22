"""Preview a part or assembly in the PythonSCAD app.

Open this file in PythonSCAD, set ``NAME`` to a key of ``PARTS`` or
``ASSEMBLIES`` (see ``python -m plotzker render --help``), and render.
"""

import sys
from pathlib import Path

try:
    _ROOT = Path(__file__).resolve().parent
except NameError:  # some PythonSCAD versions run scripts without __file__
    _ROOT = Path.cwd()
sys.path.insert(0, str(_ROOT / "src"))

from pythonscad import show

from plotzker.assemblies import ASSEMBLIES
from plotzker.parts import PARTS

NAME = "skeleton"

show({**PARTS, **ASSEMBLIES}[NAME].build())
