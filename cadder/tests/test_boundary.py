"""cadder stands on its own: no module imports a project's code."""

import pkgutil
import subprocess
import sys

import cadder

#: run inside FreeCAD's Python, not importable here
FREECAD_ONLY = {"cadder.freecad.build", "cadder.fem.viz_render", "cadder.__main__"}


def test_every_module_imports_without_any_project() -> None:
    modules = [
        m.name
        for m in pkgutil.walk_packages(cadder.__path__, "cadder.")
        if m.name not in FREECAD_ONLY
    ]
    code = (
        "import importlib, sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('plotzker', 'demo'):\n"
        "            raise ImportError('cadder imported ' + name)\n"
        "sys.meta_path.insert(0, Block())\n"
        f"for m in {modules!r}:\n"
        "    importlib.import_module(m)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(modules) > 30
