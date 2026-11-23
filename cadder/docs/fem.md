# FEM checks

How cadder checks that a part withstands its loads: how to write a part's FEM specification, how
to run a check, and how to read a result. Code: `cadder.fem` (the runner), `cadder.part` (the
specification), `cadder.regions` (where loads, supports and limits act). A project keeps its own
list of which parts need a check, its materials and print profiles, and its shared load values.

## When a check is needed

After a **new structural part**, or a **significant change** to one, and after changing its FEM
spec. Significant means anything that affects the load path: thickness, ribs, holes, fillets,
material, print profile, print orientation. Clearance tweaks and cosmetic changes don't count.

The `structural` flag on a `MaterialPart` is what counts; `cadder fem-status` lists every part
with its state: no material or FEM data yet, no spec yet, never checked, the last verdict, or
**STALE** when the part's properties or its geometry changed since that verdict.

## Defining a part's FEM spec

Any `MaterialPart` (a plate, a purchased part) can be checked; a `PrintedPart` adds the print
profile and its knockdowns. The part is registered in the project's `parts` registry, and
`cadder part NAME [--json]` prints it.

- **Frame.** `frame="installed"` (the part's assembly frame, easiest for loads; the part then
  gives that geometry as `analysis`) or the default `"output"` frame of its `build` (shown as
  `"print"` for a printed part). `build_direction` is the layer normal pointing up from the bed,
  in that frame: layers are perpendicular to it. Printed parts are transversely isotropic about
  it (`material_axis`).
- **Units.** mm, N, MPa, degrees, mm/s².
- **Regions** (`cadder.regions`): `Box` and `Cylinder` (axis x, y or z; `inner_radius`
  makes a ring). Loads and supports act on the **surface** that a region covers; a region may cover
  part of a face (the covered area is sampled, so it doesn't depend on the mesh). `facing` keeps
  only faces whose **outward normal** points that way (within `facing_tol_deg`), so to push on a
  hole wall in +x use `facing=(-1, 0, 0)`. Displacement limits look at the **mesh nodes** inside
  the region. Keep regions to a real contact area; a project's tests can check that each one
  touches its part (`cadder.testing`).
- **Loads** (`LoadCase`): `Force` (total vector, spread over the covered area; `bearing=True` for
  an axle in a bore: the share of each face falls off with the cosine of its angle to the force), `Moment` (a pure
  couple as linearly varying forces), `Acceleration` (inertia of the whole part). Give each case a
  `source`; keep `assumed=True` until a number is measured. `sustained=True` for loads that act
  continuously (belt tension, a spring): they are judged against the material's creep-reduced
  strength. Keep magnitudes shared between parts in one project module, not repeated per part.
- **Supports:** a region held fixed in the directions marked in `constrain`. Make the set
  statically determinate (no rigid-body motion) and say in the description what it stands for.
  Supports are fixed constraints: no contact, no bolt preload. Friction of a foot clamped by a
  screw can be modeled as a bonded zone of radius `BOND_RADIUS` (8 mm) round the screw
  (`regions.bond_zone`) on top of a z-only support for the rest of the foot. Where a stiff part
  holds a seat, the seat is a support in that direction, not a load.
- **Displacement limits** (`DisplacementLimit`): per region and direction; the default when a part
  states none is 0.1 mm magnitude. Several limits on one region give directional budgets.
- **Safety factor:** `FemSpec.safety_factor` (default 3), overridable per load case.
- **Parts that share a design** build their spec from one description placed in each part's
  frame with a `Placement` (`cadder.regions`); an exact mirror image is a part with `mirror_of`
  set, covered by the original's check.

Materials and print profiles are the project's (a materials TOML and a profiles folder, read with
`cadder.materials.MaterialLibrary`). A profile's stiffness and strength factors stand in for
infill; a material's `sustained_factor` is the creep allowance. Treat them as assumptions until
measured.

## Running a check

```
cadder fem NAME... [--viz] [--refine auto|always|never] [--size MM] [--uniform]
                   [--no-record] [--out DIR]
```

It needs gmsh and CalculiX (bundled in FreeCAD.app, or set `CADDER_FREECAD_BIN_DIR`). The part is
exported in its analysis frame with 20-facet holes (`CADDER_FN=20`, in a subprocess), cleaned,
meshed (quadratic tetrahedra, fine near loads and supports) and solved per load case. A second,
finer mesh is solved only when some criterion is between **0.6 and 1.6** of its limit (or with
`--refine always`), and then the two are compared. Load cases that are multiples of each other
are solved once. A small part takes about 10 s, a large bracket a minute or two with pictures.

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

## Assembly checks: deflections and play that add up

A part's check holds its neighbours rigid, so each part can pass while the pair does not: a part
that tilts in a sliding fit by its clearance has no stiffness there, so the FEM cannot find it,
while its neighbour bends at the same time.

An `AssemblyCheck` (`cadder.assembly`, the project's `assembly_checks` registry) lists member parts
and, per limit, the terms that add up: a member's displacement limit from its recorded result, or
a rigid term computed from geometry by the project (play in a fit). The total is judged against
the sum of the members' own limits, with the same PASS/MARGINAL/FAIL bands. `cadder fem` runs it
from the recorded member results, and also after a `fem` of all its members. It writes
`fem/results/<assembly>/report.md` and `result.json` and records the verdict in
`fem/verdicts.toml`; `fem-status` flags it stale when a member's recorded verdict changed.

## Limits of the method

- FDM parts are not solid: the infill knockdown is a guess, and layer adhesion and under-extrusion
  vary. Expect ±30-50 % on stress and stiffness; hence the large safety factors.
- No contact, friction, bolt preload or nonlinear material; bolted joints are supports.
- Loads are uniform traction over the covered area unless `bearing=True` (axle bores); a flat
  patch can put a stress step at its edge.
- Thin features loaded on small patches, sharp inside corners and couples applied on thin
  surfaces can give mesh-dependent local stresses. Read the pictures, not only the numbers.
- One part at a time: effects across a machine (shaft sag, beam bending) need hand calculations
  or an assembly check.
