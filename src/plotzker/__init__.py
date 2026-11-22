"""Parametric CAD for the DIY pen plotter, written for PythonSCAD.

Layout:
    geometry     rendering settings ($fn) and helpers (teardrop holes...)
    hardware     vendor-part dimensions and simple models (docs/hardware.md)
    params       shared design parameters, derived values, design checks
    parts        printable parts, one module each, in print orientation
    assemblies   fit-check assemblies (parts + hardware)
    build        CLI: ``python -m plotzker {check,stl,render,all}``
"""

__version__ = "0.1.0"
