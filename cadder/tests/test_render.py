"""PNG rendering: the driver's import paths and failure detection (no PythonSCAD needed)."""

import subprocess
import sys
from pathlib import Path

from demo.project import PROJECT

import cadder
from cadder.render import driver_paths, render_failed


def test_driver_paths_include_cadder_and_site_packages() -> None:
    first, last = driver_paths(PROJECT)
    cadder_root = str(Path(cadder.__file__).resolve().parent.parent)
    assert cadder_root in first
    assert first[0] == str(PROJECT.root / PROJECT.source_dirs[0])
    assert last and all(p not in first for p in last)


def test_a_traceback_counts_as_a_failed_render(tmp_path: Path) -> None:
    image = tmp_path / "x.png"
    image.write_bytes(b"png")
    assert not render_failed(0, image, "Total rendering time: 0:00:00.1")
    assert render_failed(0, image, "Traceback (most recent call last):\n  ...\nImportError")
    assert render_failed(1, image, "")
    assert render_failed(0, tmp_path / "missing.png", "")


def test_geometry_does_not_load_the_cpsk_solver() -> None:
    """The solver's native extension can't load in the signed PythonSCAD app."""
    code = "import sys, cadder.geometry; print('planegcs' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
