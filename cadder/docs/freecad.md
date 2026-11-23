# FreeCAD assemblies

`cadder freecad [NAMES] [--export-only]` builds each of the project's FreeCAD assemblies
(`Project.freecad_assemblies`) into `freecad/<name>.FCStd`, a FreeCAD 1.x Assembly whose parts
can be dragged along their joints. The project only *defines* an assembly, in plain Python
(`cadder.freecad.model`); cadder exports and builds it. Needs FreeCAD 1.x for the build
(`freecadcmd`, found in `CADDER_FREECAD_BIN_DIR`); the export needs only PythonSCAD.

## Defining an assembly

```python
from cadder.freecad import Body, Component, FreeCadAssembly, Joint

MACHINE = FreeCadAssembly(
    name="Machine",  # freecad/Machine.FCStd
    label="My machine",
    description="...",
    components=components,  # () -> [Component(name, solid, body, color, shape=None)]
    bodies=(Body("base", root="baseboard", grounded=True), Body("slide", root="carriage")),
    joints=joints,  # () -> [Joint(kind, a, b, origin, direction, label, limits)]
    metadata=metadata,  # () -> {...}: the reference pose etc., kept in the manifest
)
```

- **Components** are the objects of the assembly: a part, a purchased part, or a group of
  fasteners (a list of solids is united), placed in the assembly frame, each in one rigid
  **body**.
- **Bodies:** every component is held to its body's root by a Fixed joint, which the builder adds
  itself; one body is grounded.
- **Joints** give the motion: `Slider`, `Revolute`, `Cylindrical`, `Ball` or `Fixed`, between two
  components, with a frame (`origin`, `direction` = the joint's z axis) in the assembly frame and
  optional `limits` (length or angle from the modeled pose). A joint between bodies carries one
  body on another; a joint inside a body (a wheel on its axle) frees its second end (`b`) from the
  body's Fixed joint. Don't close loops (two sliders on parallel shafts): the solver
  over-constrains.
- `Components` is a list with an `add(name, solid, body, color, ...)` shorthand.
- `assembly.check()` (run by the export) catches duplicate component names, a ground count other
  than one, unknown bodies, roots and joint ends.

## Export and build

1. **Export** (`cadder.freecad.export`): each component is exported to an STL. Components that
   are the same shape in another place or orientation share one STL: only proper rotations that
   map the axes onto themselves are tried (a mirror image is a different shape). The shared file
   is named after `Component.shape`, or the first component's name without a side, position or
   number suffix (`_L`, `_top`, `_2`). Output: `freecad/<name>/stl/*.stl` and
   `freecad/<name>/manifest.json`.
2. **Build** (`cadder.freecad.build`, run by `freecadcmd` with the manifest path in
   `CADDER_FREECAD_MANIFEST`; no GUI or display needed, so it runs in CI): one `App::Part` (mesh)
   per distinct shape (shared ones are hidden masters in a hidden "Parts" group, the assembly
   holds an `App::Link` per use), the grounded body, the Fixed joints, the explicit joints, then
   `solve()`. It writes `GuiDocument.xml` into the file itself (visibility, colors and the
   joints' Python view providers, from the prototypes in `gui_document.xml`), which FreeCAD
   otherwise only stores when saving from the GUI: without it the file opens with everything
   hidden and the joints fail to recompute.

`--export-only` stops after step 1.

## The manifest (version 1)

```
{"version", "name", "label", "description", "output": "<out>/<name>.FCStd",
 "components": [{"name", "body", "color", "transparency", "stl", "center", "rotation"}],
 "bodies": [{"name", "root", "grounded"}],
 "joints": [{"kind", "a", "b", "origin", "direction", "label", "limits"}],
 "metadata": {...}}
```

A component's `rotation` (a 3×3 integer matrix, row by row) about its bounding-box `center` takes
the shared mesh to the component's place.

## Limitations

- Parts are meshes: no faces to pick, so extra joints go on the part origins or by script.
- Travel limits are stored on the joints, but `Assembly.solve()` from a script does not enforce
  them.
- No coupled motion: no belt, gear or rack-and-pinion joints.
