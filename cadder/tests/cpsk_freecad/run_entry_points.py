"""Run with freecadcmd: the addon's File menu entry points (Init.py, importCPSK) without the GUI.

Environment: ``CPSK_ADDON`` (the addon folder), ``CPSK_SAMPLE`` (a ``.cpsk`` file) and
``CPSK_ENTRY_OUT`` (output folder, gets ``results.json`` and ``export.cpsk``).
"""

import json
import os
import runpy
import sys

import FreeCAD as App

ADDON = os.environ["CPSK_ADDON"]
OUT = os.environ["CPSK_ENTRY_OUT"]
sys.path.insert(0, ADDON)  # as FreeCAD does for a Mod folder; cpsk_core is found by the addon
runpy.run_path(os.path.join(ADDON, "Init.py"))

import importCPSK  # noqa: E402

results = {"import_type": App.getImportType("cpsk"), "export_type": App.getExportType("cpsk")}
importCPSK.insert(os.environ["CPSK_SAMPLE"], "Inserted")
doc = App.getDocument("Inserted")
sketch = next(o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject")
results["inserted"] = [sketch.Label, sketch.solve(), int(sketch.DoF)]
importCPSK.export([sketch], os.path.join(OUT, "export.cpsk"))
before = set(App.listDocuments())
importCPSK.open(os.environ["CPSK_SAMPLE"])
results["opened"] = sorted(set(App.listDocuments()) - before)
try:
    importCPSK.export([], os.path.join(OUT, "none.cpsk"))
except ValueError as e:
    results["refused"] = str(e)
with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(results, f)
