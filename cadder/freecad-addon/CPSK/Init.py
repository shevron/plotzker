# CPSK addon for FreeCAD: registers .cpsk sketches with File > Open, Import and Export.
# FreeCAD runs this file at start-up (also in freecadcmd); importCPSK does the work.
import FreeCAD

FreeCAD.addImportType("CPSK sketch (*.cpsk)", "importCPSK")
FreeCAD.addExportType("CPSK sketch (*.cpsk)", "importCPSK")
