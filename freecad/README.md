# FreeCAD assembly

`make freecad` builds `PenPlotter.FCStd`, a FreeCAD 1.x Assembly of the machine (same solid
model as `assemblies/machine.py`, at mid-travel, pen up). Two steps:

1. `python -m plotter_cad freecad` cuts the model into 79 named components (printed parts,
   purchased parts, fasteners grouped per place) in the machine frame. Components that are the
   same shape (V-wheels, SK10s, SCS10UU, motors, pulleys, idlers, runners and beam, ...) share
   one STL: → 56 files in `stl/` plus `components.json` (rigid bodies, colors, joint axes,
   travel, and each component's placement).
2. `freecadcmd build_assembly.py` (no GUI or display needed, so it runs in CI) creates one
   `App::Part` (mesh) per distinct shape (the shared ones are hidden masters in a hidden
   "Parts" group, the assembly holds an `App::Link` per use), grounds the baseboard and adds
   the joints. It then writes `GuiDocument.xml` into the file itself (copied from the prototypes in `gui_document.xml`, with lxml, which FreeCAD's Python ships):
   visibility, colors and the joints' Python view providers, which FreeCAD otherwise only
   stores when saving from the GUI. Without it the file opens with everything hidden and the
   joints fail to recompute.

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

- Parts are meshes: no faces to pick, so extra joints go on the part origins or by script.
- Travel limits are stored on the joints but `Assembly.solve()` from a script does not enforce
  them; not checked in the GUI.
- The belts do not couple the motion: no belt/rack-and-pinion joints, the horn is not linked to
  the pen slide, V-wheels do not roll with the carriage. The upper Y belt runs (they change
  length with the gantry) are left out.
- Joint frames come from `params`; the machine at mid-travel is the reference pose.
