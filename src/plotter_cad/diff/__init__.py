"""Visual design diff between two revisions (``python -m plotter_cad diff``).

Phase 1 (T3.20): build every printable part at two git revisions (or the working tree), compare
the meshes and report which parts were added, removed or changed. The modules:

- :mod:`~plotter_cad.diff.stlio`: read an STL and measure it (volume, bounding box, hashes).
- :mod:`~plotter_cad.diff.snapshot`: build the parts of one revision into a cached directory.
- :mod:`~plotter_cad.diff.compare`: compare two snapshots and format the result.

Later phases add the HTML viewer, boolean added/removed meshes and the assembly instance diff.
"""
