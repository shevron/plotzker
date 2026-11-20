# FEM checks of printed parts

How the project checks that printed parts withstand their loads, how to define a part's FEM
specification, and how to read a result. The design of the tooling and its history is in
[`fem-subagent-plan.md`](fem-subagent-plan.md). The checks are done by the `fem-analyst`
sub-agent (`.claude/agents/fem-analyst.md`), which runs the commands below and interprets the
output.

## When a check is required

After a **new structural part**, or a **significant change** to one, and after changing its FEM
spec. Significant means anything that affects the load path: thickness, ribs, holes, fillets,
material, print profile, print orientation. Clearance tweaks and cosmetic changes don't count.

| Part | Structural? | State |
|------|-------------|-------|
| `x_idler_slider`, `x_idler_mount`, `gantry_end_bracket_left` | yes (belt tension) | defined, checked |
| `gantry_end_bracket_right` | yes (mirror of the left, plus loom anchor holes) | to define |
| `x_motor_mount`, `y_motor_mount_left/right`, `y_idler_mount_left/right`, `y_idler_slider_left/right` | yes (belt tension) | to define |
| `x_carriage`, `pen_holder_body`, `pen_slide` | yes (wheel loads, pen pressure, inertia) | to define |
| `tension_idler_rail`, `tension_idler_slider` | prototype of the tensioner | not used in the machine |
| `belt_clamp` | carries belt tension through two screws | to decide |
| `zrib_hanger` | light (board weight) | to decide |
| `loom_anchor`, `loom_rail`, `zrib_guard` | no | not structural |

This table is a proposal; a part's `structural` flag in its `Part` definition is what counts.

## Defining a part's FEM spec

A part is a `Part` (`src/plotter_cad/part.py`) defined at the end of its module and registered
in `parts/__init__.py` (`PARTS`). `python -m plotter_cad part NAME [--json]` prints it.

- **Frame.** `frame="installed"` (the part's assembly frame, easiest for loads) or `"print"`.
  `build_direction` is the layer normal pointing up from the bed, in that frame: layers are
  perpendicular to it. Printed parts are transversely isotropic about it.
- **Units.** mm, N, MPa, degrees, mm/s².
- **Regions** (`src/plotter_cad/regions.py`): `Box` and `Cylinder` (axis x, y or z; `inner_radius`
  makes a ring). Loads and supports act on the **surface** that a region covers; a region may cover
  part of a face (the covered area is sampled, so it doesn't depend on the mesh). `facing` keeps
  only faces whose **outward normal** points that way (within `facing_tol_deg`), so to push on a
  hole wall in +x use `facing=(-1, 0, 0)`. Displacement limits look at the **mesh nodes** inside
  the region. Keep regions to a real contact area: `tests/test_part.py` checks each one touches
  the part.
- **Loads** (`LoadCase`): `Force` (total vector, spread over the covered area), `Moment` (a pure
  couple as linearly varying forces), `Acceleration` (inertia of the whole part). Give each case a
  `source`; keep `assumed=True` until a number is measured. `sustained=True` for loads that act
  continuously (belt tension): they are judged against the material's creep-reduced strength.
  Magnitudes shared between parts live in `src/plotter_cad/loads.py`.
- **Supports:** a region held fixed in the directions marked in `constrain`. Make the set
  statically determinate (no rigid-body motion) and say in the description what it stands for.
  Supports are fixed constraints: no contact, no friction, no bolt preload.
- **Displacement limits** (`DisplacementLimit`): per region and direction; the default when a part
  states none is 0.1 mm magnitude. Several limits on one region give directional budgets.
- **Safety factor:** `FemSpec.safety_factor` (default 3), overridable per load case.

Materials are in `src/plotter_cad/materials.toml`, print profiles in `src/plotter_cad/profiles/`
(`default.toml` is PETG, 0.6 mm nozzle, 0.3 mm layers, 3 perimeters, 20 % gyroid). The profile's
stiffness and strength factors (0.6) stand in for infill; a material's `sustained_factor` (0.5) is
the creep allowance. All of these are assumptions until measured.

## Running a check

```
python -m plotter_cad fem NAME... [--viz] [--refine auto|always|never] [--size MM] [--uniform]
                                  [--no-record] [--out DIR]
```

or `make fem NAMES="..."`. It needs gmsh and CalculiX (bundled in FreeCAD.app, or set
`PLOTTER_FEM_BIN_DIR`). The part is exported in its analysis frame with 20-facet holes
(`PLOTTER_FN=20`), cleaned, meshed (quadratic tetrahedra, fine near loads and supports) and
solved per load case. A second, finer mesh is solved only when some criterion is between **0.6
and 1.6** of its limit (or with `--refine always`), and then the two are compared. Load cases
that are multiples of each other are solved once. Typical times: slider about 10 s, mount about
20 s, bracket about 80 s with pictures.

**Official and diagnostic runs.** A plain run is the official check: it writes
`fem/results/NAME/` (git-ignored: `report.md`, `result.json`, `part.json`, `final.msh`,
`final_<case>.inp/.frd`, `viz/` with `--viz`) and updates `fem/verdicts.toml` (committed: last
verdict, date, a hash of the cleaned STL and a hash of the part properties; if either hash
changes the verdict is stale and the check must be repeated). **Diagnostic runs** (a finer mesh,
a different size) use `--no-record --out DIR` so they overwrite neither the official result nor
the verdict. The official verdict is always the one from the default settings.

## Reading a result

- **Criteria.** Strength: **utilization** = failure index × safety factor, 1.0 at the allowable.
  The failure index is the larger of an in-plane mode (largest in-plane principal stress over the
  in-plane strength) and an interlayer mode (tension across layers plus shear between layers over
  the interlayer strength, delamination). The report's detail line for strength gives the
  governing point, the stress components there in MPa with their allowables, and the distance to
  the nearest load or support patch. Displacements are the largest absolute value along the
  stated direction over the nodes of the region.
- **Thresholds.** Status: PASS up to 85 % of a limit, MARGINAL up to 100 %, FAIL beyond. A second
  mesh is solved when a criterion is between 0.6 and 1.6. The report flags a possible
  sharp-corner singularity when the peak stress changes by more than 25 % between meshes.
  Sanity checks: reactions balance the loads within 1 %, compliance (external work) agrees
  between the two meshes within 5 %, mesh volume within 2 % of the STL.
- **Verdict** of a part: the worst criterion; **INCONCLUSIVE** if a sanity check failed.
- **Which load case matters.** Every case is judged; the one with the highest utilization governs
  the verdict, and it is not always the larger load (a sustained case can govern because of the
  creep factor). Look at the pictures of that case.
- **Hot spots.** Strength is judged away from the edges of loaded and supported patches (within
  1.5 element sizes), where stresses are artifacts; the report states the raw peak when it
  exceeds the limit, and how much the peak changed between meshes.
- **Pictures** (`viz/`): deformed shape over a ghost, colored by utilization (blue fine, orange at
  the allowable, red over) or displacement; a magenta ball marks the governing point.

## Limits of the method

- FDM parts are not solid: the infill knockdown is a guess, and layer adhesion and under-extrusion
  vary. Expect ±30-50 % on stress and stiffness; hence the large safety factors. Calibrating
  against a loaded printed part is postponed.
- No contact, friction, bolt preload or nonlinear material; bolted joints are supports.
- Loads are applied as uniform traction over the covered area (a bearing load would really be
  concentrated at the center of a contact); this can put a stress step at the patch edge.
- Thin features loaded on small patches, sharp inside corners and couples applied on thin
  surfaces can give mesh-dependent local stresses. Read the pictures, not only the numbers.
- Gantry-level effects (shaft sag, extrusion bending) are hand calculations, not meshed.
