"""Run with freecadcmd: build every case in FreeCAD, solve it, export it with the plugin.

Environment: ``CPSK_EXPORT_OUT`` (output folder) and ``CPSK_PATHS`` (``os.pathsep``-separated
folders holding ``cpsk_core``, ``cpsk_freecad`` and these cases). Writes ``<case>.cpsk`` for each
case that exports and ``results.json``: per case, FreeCAD's solved geometry, its degrees of
freedom, and the export's errors or warnings.
"""

import json
import math
import os
import sys
import traceback

import FreeCAD as App
import Part
import Sketcher

sys.path[:0] = os.environ["CPSK_PATHS"].split(os.pathsep)

from cases import C  # noqa: E402
from export_cases import X  # noqa: E402

from cpsk_core import CpskExportError  # noqa: E402
from cpsk_freecad import export_sketch  # noqa: E402

OUT = os.environ["CPSK_EXPORT_OUT"]
V = App.Vector
Z = V(0, 0, 1)
DIMENSIONAL = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}


def geometry(g):
    kind = g[0]
    if kind == "point":
        return Part.Point(V(g[1], g[2], 0))
    if kind == "line":
        return Part.LineSegment(V(g[1], g[2], 0), V(g[3], g[4], 0))
    if kind == "circle":
        return Part.Circle(V(g[1], g[2], 0), Z, g[3])
    if kind == "ellipse":
        return Part.Ellipse(V(g[1], g[2], 0), g[3], g[4])
    return Part.ArcOfCircle(Part.Circle(V(g[1], g[2], 0), Z, g[3]), math.radians(g[4]), math.radians(g[5]))


def dump(geo):
    name = type(geo).__name__
    if name == "Point":
        return ["point", geo.X, geo.Y]
    if name == "LineSegment":
        return ["line", geo.StartPoint.x, geo.StartPoint.y, geo.EndPoint.x, geo.EndPoint.y]
    if name == "Circle":
        return ["circle", geo.Center.x, geo.Center.y, geo.Radius]
    if name == "ArcOfCircle":
        first, last = geo.FirstParameter, geo.LastParameter
        return ["arc", geo.Center.x, geo.Center.y, geo.Radius, *map(math.degrees, (first, last))]
    return [name]


def build(doc, case):
    for name, label, properties in case.get("varsets", []):
        varset = doc.addObject("App::VarSet", name)
        varset.Label = label
        for prop, type_id, value, expression, description in properties:
            varset.addProperty(type_id, prop, "Base", description)
            setattr(varset, prop, value)
            if expression:
                varset.setExpression(prop, expression)
    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    for i, g in enumerate(case.get("external", [])):
        line = doc.addObject("Part::Line", f"External{i}")
        line.X1, line.Y1, line.X2, line.Y2 = g[1:5]
        line.Z1 = line.Z2 = 0
        doc.recompute()
        sketch.addExternal(line.Name, "Edge1")
    for g in case["geometry"]:
        index = sketch.addGeometry(geometry(g), False)
        if g[-1] == "block":
            sketch.addConstraint(Sketcher.Constraint("Block", index))
    for kind, args, value, driving, *rest in case["constraints"]:
        extra = rest[0] if rest else {}
        if kind in DIMENSIONAL:
            number = 1.0 if value is None else value
            if kind == "Angle":
                number = math.radians(number)
            index = sketch.addConstraint(Sketcher.Constraint(kind, *args, number))
        else:
            index = sketch.addConstraint(Sketcher.Constraint(kind, *args))
        if not driving:
            sketch.setDriving(index, False)
        if "name" in extra:
            sketch.renameConstraint(index, extra["name"])
        if "expression" in extra:
            sketch.setExpression(f"Constraints.{extra['name']}", extra["expression"])
        if not extra.get("active", True):
            sketch.setActive(index, False)
    doc.recompute()
    sketch.solve()
    doc.recompute()
    return sketch


results = {}
for case in C + X:
    name = case["name"]
    doc = App.newDocument(name)
    result = results[name] = {}
    try:
        sketch = build(doc, case)
        result["geometry"] = [dump(g) for g in sketch.Geometry]
        result["dof"] = sketch.solve() == 0 and int(sketch.DoF)
        path = os.path.join(OUT, f"{name}.cpsk")
        try:
            warnings = export_sketch(sketch, path)
            result["file"] = path
            result["warnings"] = [[d.code, d.message] for d in warnings]
        except CpskExportError as e:
            result["errors"] = [[list(d.ids), d.message] for d in e.diagnostics]
    except Exception:  # noqa: BLE001: report it to the test
        result["crash"] = traceback.format_exc()
    App.closeDocument(doc.Name)

with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(results, f, indent=1)
print("cases:", len(results))
