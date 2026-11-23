"""Finite-element checks of printable parts (gmsh + CalculiX). See ``docs/fem.md`` (cadder).

Pipeline: part STL (analysis frame, coarse facets) → cleaned STL → tet10 mesh → CalculiX per
load case → criteria (failure index, displacement limits) → verdict, report and pictures.
"""
