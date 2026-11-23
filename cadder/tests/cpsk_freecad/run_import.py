"""Run with freecadcmd: import CPSK files with the plugin, then export the result again.

Environment: ``CPSK_IMPORT_IN`` (``os.pathsep``-separated ``.cpsk`` files), ``CPSK_IMPORT_OUT``
(output folder) and ``CPSK_PATHS`` (folders holding ``cpsk_core`` and ``cpsk_freecad``). Writes
``<stem>.cpsk`` (the re-export) for each file and ``results.json``: per file, the import's
warnings or errors, FreeCAD's degrees of freedom, constraints, expressions and VarSet
properties, and the re-export's warnings or errors.
"""

import json
import os
import sys
import traceback

import FreeCAD as App

sys.path[:0] = os.environ["CPSK_PATHS"].split(os.pathsep)

from cpsk_core import CpskError  # noqa: E402
from cpsk_freecad import export_sketch, import_sketch  # noqa: E402

OUT = os.environ["CPSK_IMPORT_OUT"]
results = {}
for path in os.environ["CPSK_IMPORT_IN"].split(os.pathsep):
    stem = os.path.splitext(os.path.basename(path))[0]
    doc = App.newDocument("Import")
    result = results[stem] = {}
    try:
        try:
            sketch, warnings = import_sketch(doc, path)
        except CpskError as e:
            result["import_errors"] = [[list(d.ids), d.message] for d in e.diagnostics]
            continue
        result["import_warnings"] = [[d.code, list(d.ids)] for d in warnings]
        result["dof"] = sketch.solve() == 0 and int(sketch.DoF)
        result["label"] = sketch.Label
        result["constraints"] = [
            [c.Type, c.Name, c.Driving, c.IsActive] for c in sketch.Constraints
        ]
        result["expressions"] = [list(item) for item in sketch.ExpressionEngine]
        varsets = [o for o in doc.Objects if o.TypeId == "App::VarSet"]
        result["varsets"] = [
            [
                v.Label,
                [[p, getattr(getattr(v, p), "Value", getattr(v, p))] for p in v.PropertiesList],
            ]
            for v in varsets
        ]
        out = os.path.join(OUT, f"{stem}.cpsk")
        try:
            result["export_warnings"] = [[d.code, d.message] for d in export_sketch(sketch, out)]
            result["file"] = out
        except CpskError as e:
            result["export_errors"] = [[list(d.ids), d.message] for d in e.diagnostics]
    except Exception:  # noqa: BLE001: report it to the test
        result["crash"] = traceback.format_exc()
    finally:
        App.closeDocument(doc.Name)

with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(results, f, indent=1)
print("files:", len(results))
