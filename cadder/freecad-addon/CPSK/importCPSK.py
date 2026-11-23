"""FreeCAD's File > Open, Import and Export entry points for CPSK sketches.

FreeCAD calls ``open(filename)``, ``insert(filename, docname)`` and
``export(objects, filename)`` for the types registered in ``Init.py``. Problems are reported in
the Report view; with the GUI up, a refused import or export is also shown in a dialog. Without
the GUI (``freecadcmd``), errors are raised as :class:`cpsk_core.CpskError`.
"""

from __future__ import annotations

import os
from typing import Any

import FreeCAD

from cpsk_freecad import CpskError, Diagnostic, export_sketch, import_sketch  # finds cpsk_core

_TITLE = "CPSK sketch"


def open(filename: str) -> None:  # FreeCAD's importer protocol: shadows the builtin
    """File > Open: a new document holding the imported sketch."""
    name = os.path.splitext(os.path.basename(filename))[0]
    doc = FreeCAD.newDocument(_document_name(name))
    _import(doc, filename)


def insert(filename: str, docname: str) -> None:
    """File > Import: add the sketch (and its VarSet) to a document."""
    try:
        doc = FreeCAD.getDocument(docname)
    except NameError:
        doc = FreeCAD.newDocument(docname)
    _import(doc, filename)


def export(objects: list[Any], filename: str, *options: Any) -> None:
    """File > Export: write the one selected sketch."""
    sketches = [o for o in objects if o.TypeId == "Sketcher::SketchObject"]
    if len(sketches) != 1:
        _fail(f"Select exactly one sketch to export as CPSK ({len(sketches)} selected).")
        return
    sketch = sketches[0]
    try:
        warnings = export_sketch(sketch, filename)
    except CpskError as e:
        _refused(f"{sketch.Label} cannot be exported as CPSK 0.1", e)
        return
    _report(warnings)
    FreeCAD.Console.PrintMessage(f"CPSK: exported {sketch.Label} to {filename}\n")


def _import(doc: Any, filename: str) -> None:
    try:
        sketch, warnings = import_sketch(doc, filename)
    except CpskError as e:
        _refused(f"{os.path.basename(filename)} cannot be imported", e)
        return
    _report(warnings)
    FreeCAD.Console.PrintMessage(f"CPSK: imported {filename} as {sketch.Label}\n")
    if FreeCAD.GuiUp:
        import FreeCADGui

        FreeCADGui.SendMsgToActiveView("ViewFit")


def _report(warnings: list[Diagnostic]) -> None:
    for diagnostic in warnings:
        FreeCAD.Console.PrintWarning(f"CPSK: {diagnostic}\n")


def _refused(summary: str, error: CpskError) -> None:
    lines = [str(d) for d in error.diagnostics]
    FreeCAD.Console.PrintError(f"CPSK: {summary}:\n" + "".join(f"  {ln}\n" for ln in lines))
    if not FreeCAD.GuiUp:
        raise error
    _dialog(f"{summary}:", "\n".join(f"• {ln}" for ln in lines))


def _fail(message: str) -> None:
    FreeCAD.Console.PrintError(f"CPSK: {message}\n")
    if not FreeCAD.GuiUp:
        raise ValueError(message)
    _dialog(message, "")


def _dialog(text: str, details: str) -> None:
    import FreeCADGui
    from PySide import QtGui

    box = QtGui.QMessageBox(FreeCADGui.getMainWindow())
    box.setIcon(QtGui.QMessageBox.Warning)
    box.setWindowTitle(_TITLE)
    box.setText(text)
    if details:
        box.setInformativeText(details)
    box.exec_()


def _document_name(label: str) -> str:
    """A valid FreeCAD document name for a file name."""
    cleaned = "".join(c if c.isalnum() else "_" for c in label)
    return cleaned if cleaned[:1].isalpha() else f"Sketch_{cleaned}"
