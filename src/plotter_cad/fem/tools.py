"""Locating the external solvers (gmsh and CalculiX), which ship inside FreeCAD."""

import os
import shutil
from pathlib import Path

#: Where FreeCAD.app keeps ``ccx``, ``gmsh`` and its Python (override with ``PLOTTER_FEM_BIN_DIR``).
FREECAD_BIN_DIR = Path("/Applications/FreeCAD.app/Contents/Resources/bin")


def find_tool(name: str) -> Path:
    """Path of the executable ``name`` (``ccx``, ``gmsh``, ``python``)."""
    folder = Path(os.environ.get("PLOTTER_FEM_BIN_DIR", FREECAD_BIN_DIR))
    candidate = folder / name
    if candidate.is_file():
        return candidate
    found = shutil.which(name)
    if found and name != "python":
        return Path(found)
    raise RuntimeError(
        f"{name} not found in {folder}. Install FreeCAD 1.x (it bundles gmsh and CalculiX) or "
        "set PLOTTER_FEM_BIN_DIR to the folder holding them."
    )


def tools_available() -> bool:
    """Whether both solvers can be found."""
    try:
        find_tool("ccx")
        find_tool("gmsh")
    except RuntimeError:
        return False
    return True
