# FreeCAD assembly

`make freecad` (`python -m plotzker freecad`) builds `PenPlotter.FCStd`, a FreeCAD 1.x Assembly
of the machine (same solid model as `assemblies/machine.py`, at mid-travel, pen up). The
plotter only *defines* the assembly (`src/plotzker/freecad_assembly.py`: components, rigid
bodies, joints); cadder exports and builds it. How that works, the manifest and the general
limitations: [`cadder/docs/freecad.md`](../cadder/docs/freecad.md).

- Export: 84 named components (printed parts, purchased parts, fasteners grouped per place) in
  the machine frame; same-shape ones (V-wheels, SK10s, SCS10UU, motors, pulleys, idlers, runners
  and beam, ...) share one STL → 61 files in `PenPlotter/stl/` plus `PenPlotter/manifest.json`.
- Build: grounds the baseboard, fixes every component to its body's root and adds the joints
  below.

`python -m plotzker freecad --export-only` stops after the export (no FreeCAD needed).

Open `PenPlotter.FCStd` in FreeCAD and drag parts in the Assembly workbench.

## Joints

| Motion | Joint |
|---|---|
| Baseboard | Grounded |
| Everything screwed together (per rigid body: base, gantry, carriage, pen slide) | Fixed, to the body's root part |
| Gantry along Y | Slider, left shaft ↔ left SCS10UU block (limits ±272.4 mm); no joint on the right shaft, it would close a loop and over-constrain the solver |
| X carriage along X | Slider, beam ↔ carriage (limits ±213 mm) |
| Pen lift | Slider, pen holder body ↔ pen slide (limits 0 to −7 mm) |
| Y and X pulleys, Y and X idlers, 4 V-wheels, servo horn | Revolute |

## Limitations

Besides cadder's (meshes only, limits not enforced by a scripted `solve()`; not checked in the
GUI):

- The belts do not couple the motion: the horn is not linked to the pen slide, V-wheels do not
  roll with the carriage. The upper Y belt runs (they change length with the gantry) are left
  out.
- Joint frames come from `params`; the machine at mid-travel is the reference pose.
