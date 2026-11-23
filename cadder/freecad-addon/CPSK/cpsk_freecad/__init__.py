"""CPSK import and export for FreeCAD's Sketcher (cadder/docs/cpsk/freecad-plugin-plan.md).

Runs in FreeCAD's Python (3.11) and needs ``cpsk_core`` on the path. The modules do not import
FreeCAD themselves: they read sketches through their Python attributes.
"""

from cpsk_freecad.export_sketch import FREECAD_NAMESPACE, export_sketch, to_document

__all__ = ["FREECAD_NAMESPACE", "export_sketch", "to_document"]
