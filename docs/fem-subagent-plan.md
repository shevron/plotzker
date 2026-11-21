# Plan: FEM check sub-agent

**Status:** agreed in review; tracked as T3.18 in [`STATUS.md`](../STATUS.md). Nothing is implemented yet.

Goal: after a part or assembly is designed or significantly changed, an independent
`fem-analyst` sub-agent checks that it withstands the planned loads within the allowed
deflection, and reports pass/fail plus, optionally, pictures of how it fails.

## 1. Decisions taken in review

| # | Decision |
|---|----------|
| 1 | Everything a part needs (geometry function, material, print profile, build direction, loads, supports, FEM criteria) is defined **in Python, in one place per part** (a part class). A CLI prints a part's properties so the sub-agent never has to read CAD code. The same CLI later grows other commands (export an STL, ...). |
| 2 | All printed parts are PETG. A **default print profile** (PETG, 0.6 mm nozzle, 0.3 mm layers, 3 perimeters, 20 % gyroid infill) lives in a TOML file; a part may name another profile, which is another TOML file. |
| 3 | First parts to check: **X idler slider, X idler mount, gantry end bracket** (the most belt-loaded). |
| 4 | Allowed deflection is defined per part, with a default of **0.1 mm**, tighter for the pen. It is **directional**: e.g. the X idler may move more along the belt axis (toward the X motor) than down or sideways. |
| 5 | Loads (belt preload, carriage mass and acceleration) are unknown: start with documented `ASSUMED` values, refine after bench tests. |
| 6 | The sub-agent runs on the strongest model. |
| 7 | No calibration coupon for now. Compensate with **large safety factors**, narrow them as experience accumulates. |

## 2. Architecture

```
src/plotter_cad/
├── part.py              ← Part base class + FEM/print dataclasses (typed, validated)
├── profiles/            ← print profiles: default.toml, others as needed
├── materials.toml       ← PETG (printed, anisotropic), 6063 aluminum, steel, plywood, POM
├── parts/<part>.py      ← geometry (as today) + a `PART = ...` definition with its properties
├── fem/                 ← mesh, solve, evaluate, visualize (glue around gmsh + CalculiX)
└── build.py             ← CLI gains: `part`, `fem`
fem/results/             ← generated (git-ignored): reports, JSON, PNGs, .vtu
fem/verdicts.toml        ← committed: last verdict per part + hash of geometry and properties
.claude/agents/fem-analyst.md   ← the sub-agent definition
docs/fem.md              ← modeling conventions, material sources, how to read a report
```

`PRINTABLE_PARTS` becomes derived from the part registry, so there is one list of parts.

### 2.1 The part class

One definition per printable part, next to its geometry. It holds:

- **Identity and geometry:** name, the function that builds the part, and the frame
  (`print` or `installed`).
- **Print:** profile name (default `default`), material name, build direction as a vector
  in the chosen frame (+Z for the print frame, which is what the STL uses today).
- **FEM requirement:** `required` or `not_structural`, with a reason.
- **Supports:** where the part is held (e.g. the screw-washer footprints).
- **Load cases:** each with a name, force/moment/gravity/acceleration terms applied to a
  region, a `source` string, and an `assumed` flag.
- **Criteria:** per load case, see §4.

Regions are geometric selectors (box, sphere, cylinder, plane, or a named handle from D28
plus a radius). Because the definition is Python, loads can be computed from `params.py`
(belt geometry, tension, pulley positions) rather than copied as numbers, so they stay in
sync with the design.

### 2.2 The CLI

| Command | Output |
|---------|--------|
| `python -m plotter_cad part --list` | All parts with profile, material, FEM-required flag, last verdict (and whether it is stale) |
| `python -m plotter_cad part <name>` | Human-readable properties |
| `python -m plotter_cad part <name> --json` | Same as JSON, with regions and handles resolved to numeric coordinates: this is what the sub-agent reads |
| `python -m plotter_cad fem <name> [--viz]` | Run the check, write `fem/results/<name>/`, update the verdict |
| `make fem NAMES="..."` | Same, via the Makefile |

### 2.3 Print profiles and materials

`profiles/default.toml` holds: material, nozzle, layer height, perimeters, infill % and
pattern, plus the derived knockdown factors the FEM needs (printed solid vs. a real part
with 20 % infill). A part may name another profile (e.g. `stiff.toml`: more perimeters).

`materials.toml` holds, per material: density, in-plane and out-of-plane modulus, shear
modulus and Poisson ratio (printed materials are transversely isotropic about the build
direction), in-plane and interlayer strength, a long-term (creep) factor for constant
loads (belt tension is constant), and a `source`/`assumed` note per value. PETG values start as
conservative generic numbers marked *assumed*.

## 3. The sub-agent

**Role.** Independent verifier. The main agent writes or updates the part definition and
asks for a check; the sub-agent only evaluates it. This avoids the author grading their
own design.

**Rules (written into `.claude/agents/fem-analyst.md`).**

1. Get inputs only from `part <name> --json`; if something is missing or an `assumed` value
   dominates the result, return **needs input** with specific questions.
2. Never change loads, criteria or safety factors to make a part pass.
3. Read-only on `src/` and `docs/`; write only under `fem/results/` (and the verdict file).
4. Always run the sanity checks (below) before trusting a result.
5. Return: a per-criterion verdict table, the paths to images and reports, an
   interpretation of any failure (where, what mode, which loads), and **suggested** design
   changes (not applied).

**Tools:** Bash, Read, Write/Edit, Glob, Grep. **Model:** strongest available.
A new agent definition loads at session start, so a session restart is needed once it
exists.

## 4. Criteria and results

Per load case:

- **Strength:** failure index × safety factor ≤ 1. The index is the larger of two modes: the
  largest in-plane principal stress (tension or compression) over the in-plane strength, and tension
  across the layers combined quadratically with shear between the layers over the interlayer
  strength (shear strength assumed equal to it). A max-of-modes rule replaces Tsai-Hill, which is
  not convex when the interlayer strength is below 1/√2 of the in-plane one. Von Mises alone would
  miss delamination.
- **Displacement:** limit on a named region, as a total magnitude (default 0.1 mm) and/or
  per direction in a named frame (e.g. along the belt axis, down, sideways). The X idler
  example: generous along the belt axis, 0.1 mm down and sideways.
- **Relative displacement** between two regions, **twist or tilt** of a region (fit to the
  region's nodes), **stiffness** (N/mm).
- Optional: linear **buckling** factor, first **natural frequency**.

**Safety factors (initial, deliberately large):** 3 on strength for every load case. Loads that
act continuously (belt tension) are additionally checked against the material's *sustained
factor* (0.5, for creep), so they effectively carry a factor of 6 on short-term strength.
The print profile's infill knockdown (strength × 0.6) comes on top of both.

**Verdicts:** PASS, FAIL, MARGINAL (less than 15 % margin), INCONCLUSIVE (mesh not
converged, or sanity checks failed).

**Sanity checks, every run:** consistent units (mm, N, MPa, tonne/mm³ for CalculiX);
reactions equal applied loads; one mesh refinement, displacement must agree within 5 %;
stress peaks at point loads and sharp re-entrant corners are reported both raw and with
the singular spots excluded.

**Visual output (`--viz`):** PNG contours of failure index and displacement on the
deformed shape (scale printed on the image, undeformed ghost, peak marked, failing
criterion in the title), an overview view plus one aimed at the hot spot; `.vtu` for
ParaView or FreeCAD. The sub-agent also looks at the images and writes a short "how it
failed" note. Offscreen VTK rendering on macOS is verified in the spike; the fallback is matplotlib.

## 5. Tooling

Already installed with FreeCAD 1.1.3: `ccx` (CalculiX), `gmsh`, VTK. No new installs.
Chosen approach: our own typed glue runs gmsh and ccx directly (STL → 10-node
tetrahedra; transversely isotropic material with the orientation from the build
direction) and reads the `.frd` result. Rejected: FreeCAD's FEM Python API (GUI-shaped,
fragile headless), pip FEM libraries (Python 3.14 wheels uncertain). The F0 spike confirms
or overturns this.

## 6. Scope

- **v1: one part at a time.** Neighbors are replaced by supports or reaction loads.
  Bolted joints are modeled as a fixed washer-footprint, nut traps as part of the solid.
- **Shaft and extrusion deflection** (the 0.2–0.4 mm sag) is a closed-form hand check the
  sub-agent does as a cross-check, not a mesh.
- **Later:** assemblies with bonded contacts, calibration against a printed and loaded
  part, tighter safety factors.

## 7. Process changes (applied only once this plan is agreed)

- **README §7.1 and §7.4:** a new or significantly changed part gets a part definition and
  an FEM check before handover. "Significant" = anything affecting the load path
  (thickness, ribs, holes, fillets, material, profile, orientation); clearance tweaks do
  not count.
- **README §5 layout and §7.2/§7.4 text:** new files; the per-part "Print:" docstring line
  is replaced by the part's profile reference (see §8, item 1).
- **CLAUDE.md "Finishing a session":** one line pointing to the FEM check.
- **STATUS.md:** add the tasks below, and an "FEM" verdict note per part.
- **`docs/fem.md`:** modeling conventions and a table of which parts are FEM-required.

## 8. Things this change touches that need your decision

1. **Existing print settings in the part docstrings** (e.g. `x_idler_slider`: "0.2 mm; 4
   perimeters; 40 % infill") **disagree with the new default profile.** Proposal: the
   profile becomes the single source; docstrings point to it, and parts that need
   something else name a profile.
2. **Minimum wall (README §7.4: 1.6 mm = 4 perimeters at 0.4 mm).** With a 0.6 mm nozzle
   and 3 perimeters the wall is 1.8 mm (3 × 0.6), so the rule should be restated per profile.
3. **Tolerances in `params.TOL`** (nut slots, holes): confirmed measured with the default
   profile (PETG, 0.6 mm nozzle, 0.3 mm layers, 3 perimeters, 20 % infill), so they stay valid.
   Other profiles may need their own tolerance values.
4. **Initial assumed loads (proposal, confirmed in review):** belt preload 40 N per belt run (so
   ~80 N on the idler axle and on its tension screw), plus 20 N dynamic; carriage mass and
   acceleration only matter for the pen holder and carriage (assume 0.3 kg at 3000 mm/s²).
   **Initial directional limits (proposal):** X idler 0.3 mm along the belt axis, 0.1 mm
   other directions; pen holder 0.05 mm.

## 9. Tasks

| # | Task | Done when |
|---|------|-----------|
| F0 ✅ | Spike | The gmsh + ccx pipeline reproduces a cantilever closed-form result within 2 %, runs on the X idler slider, and offscreen rendering works; tooling choice confirmed |
| F1 ✅ | Part class, profiles, materials | `part.py`, `default.toml`, `materials.toml` exist with validation and tests; the three first parts are migrated and the `part` CLI prints them as JSON; you have reviewed the assumed loads and limits |
| F2 ✅ | Runner | `python -m plotter_cad fem <name>` produces verdicts, JSON and a Markdown report; solver benchmarks in the tests (skipped if `ccx` is missing) |
| F3 ✅ | Visualization | `--viz` produces the PNGs and `.vtu` |
| F4 ✅ | Agent and process | `.claude/agents/fem-analyst.md`, `docs/fem.md`, README/CLAUDE.md/STATUS.md edits done; a dry run on a real part gives a report you accept |
| F5 | Later | Migrate all remaining parts to part classes; assemblies with contacts; buckling/modal; calibration; `make fem-status` stale check |

## 10. Honest limits

FEM of FDM parts is typically ±30–50 % off (infill, layer adhesion, underextrusion). With
no calibration for now, the large safety factors carry that uncertainty, and the results are
best used to catch gross failures and to compare design variants.

## 11. F0 spike results (2026-11-20: done)

The chosen tooling (gmsh + CalculiX run directly from our own glue, VTK for pictures) works.
The spike scripts were scratch work; F1/F2 implement the real thing.

| Check | Result |
|-------|--------|
| Cantilever benchmark (100 × 10 × 5 mm, E 2000 MPa, tip load 1 N), tet10 from an STL | tip deflection 1.587 mm vs 1.603 mm closed form (Euler + shear): **−1.0 %**, stable over 3 mesh sizes (−1.3 / −1.1 / −1.0 %); the 1 % is the 3D clamp stiffening a beam model ignores |
| `x_idler_slider` | meshes and solves: 7.6k tets, **~2.5 s** total |
| `x_idler_mount` | meshes and solves: 9.4k tets, ~2 s |
| `gantry_end_bracket_left` | meshes and solves once the STL is cleaned and exported with 20-facet holes (27k tets, ~8 s); the raw 64-facet STL hangs the mesher |
| Offscreen picture | VTK (bundled with FreeCAD, Python 3.11) renders a displacement contour on the deformed shape to a PNG in ~2 s; no GUI needed. matplotlib fallback not needed |

**What we learned, and what F1/F2 must do about it**

1. **STL needs cleaning before meshing:** weld vertices (1e-3 mm) and drop degenerate
   triangles, both the ones with merged vertices (`x_idler_slider` had 8) and the **zero-area
   collinear ones** PythonSCAD leaves along edges where a face outline gains extra vertices
   (the gantry end bracket has 8 of them along its outboard top edge). Without it gmsh reports
   overlapping facets or "could not recover boundary mesh", and CalculiX finds non-positive
   Jacobians. **The bracket's CAD geometry is fine** (an earlier note here blamed
   non-manifold edges; those were these slivers), so no CAD change was needed.
2. **Mesh settings that worked:** keep the STL triangles as the boundary (no surface
   reparametrization; the reparametrizing route failed or hung on two of three parts) and
   use **straight-sided** 10-node tets (curved mid-nodes on the facets produce inverted
   elements). Node order is swapped for CalculiX (the last two nodes of gmsh's tet10).
3. **The 64-facet holes are too fine for FEM:** the bracket's mesher hangs on them even after
   cleaning (many tiny boundary triangles next to 3 mm elements). Exporting with a coarser facet
   count (20 for holes: 1 648 triangles instead of 4 238) fixes it: the bracket then meshes in
   1 s (27k tets) and solves in 6.6 s. F1 adds a "FEM resolution" override of `geometry.FN` /
   `FN_HOLE` to the part build.
4. **Validation in the runner:** a sealed-surface check on the STL is not reliable (slivers come
   in pairs and fool edge counting), so the runner instead trusts gmsh and CalculiX (a failed
   boundary recovery or a non-positive Jacobian aborts the run with a clear message) and compares
   the mesh volume with the part's volume.
5. **Forces:** nodal forces lumped from the surface triangles inside a load region
   (corner 0, mid-edge 1/3 of the area) reproduce the closed-form load correctly; no
   special CalculiX load cards needed.
6. **Environment:** `ccx` 2.23 and `gmsh` 4.15 are binaries (no gmsh Python module);
   mesh scripts are `.geo` files. The glue is stdlib Python in the project environment (3.14);
   only the pictures need FreeCAD's bundled Python (VTK, numpy, matplotlib), run as a subprocess.

## 12. F1 results (2026-11-20: done, awaiting your review of the assumed values)

**What exists now**

| Item | Where |
|------|-------|
| Part class: geometry function, frame, build direction, profile, material, FEM spec (load cases, supports, displacement limits, safety factor) | `src/plotter_cad/part.py` |
| Regions (box, cylinder/ring; selected by face centroid and outward normal, or by node for limits) | `src/plotter_cad/regions.py` |
| Print profile loader and `profiles/default.toml` (PETG, 0.6 mm, 0.3 mm, 3 perimeters, 20 % gyroid; stiffness and strength factors 0.6, assumed) | `print_profile.py`, `profiles/` |
| Materials loader and `materials.toml` (PETG, all values assumed) | `materials.py`, `materials.toml` |
| Assumed belt loads in one place | `loads.py` |
| CLI: `python -m plotter_cad part --list`, `part NAME`, `part NAME --json` | `build.py`, `part_report.py` |
| `PLOTTER_FN=20` environment variable lowers the facet count for FEM meshes (default 64 unchanged) | `geometry.py` |
| Registry of parts defined as `Part`; the other 18 printable parts are listed as "not yet defined" | `parts/__init__.py` (`PARTS`) |
| Definitions: `x_idler_slider`, `x_idler_mount`, `gantry_end_bracket_left` (the right bracket is a mirror, done in F5) | `PART` at the end of each module |
| Tests: profile/material loading, knockdowns, JSON output, spec validation, and that **every load, support and limit region touches the actual part** | `tests/test_part.py` |

The three parts' docstrings now point to the default profile instead of the old per-part print
settings (the other parts keep theirs until they are migrated).

**Modeling choices to review**

- **X idler slider:** the belt pulls the axle bore inboard (+x). Held by the M3 nut's seat in the
  rear wall (x only) and by the dovetail channel (y and z only), so it is statically determinate.
- **X idler mount:** the screw head pushes the end block with the same force (+x), and the slider's
  tilt adds a **couple on the ridge** (belt force × the height of the axle above the screw, ~1.2 N·m
  at preload). Held by the two rear M5 washer rings (fixed) and the foot's underside on the bracket
  (z only).
- **Gantry end bracket (left):** the X belt's reaction (mount pulls the base +x, the beam pushes
  back −x on the face plate pocket floor) plus the Y belt's two ends pulling the clamps apart
  (±y). Held by the 8 block bolts' washer rings.
- Each part has two load cases: `belt_preload` (sustained) and `belt_peak`.
- Not modeled yet: contact (supports are fixed instead of unilateral), bolt preload, weight of the
  gantry on the bracket, handling loads. The bracket's x load enters as traction on the base top.

**Assumed values to confirm (all in code, one place each)**

| Value | Now | Where |
|-------|-----|-------|
| Belt tension per run, preload / extra at peak | 40 N / +20 N | `loads.py` |
| Allowed displacement, X idler seat and slider axle | 0.3 mm along the belt, 0.1 mm sideways and vertical (each part; the two add up in the assembly) | `PART` of each module |
| Allowed displacement, bracket beam seat | 0.1 mm in x, y and z | `gantry_end_bracket.py` |
| Safety factor | 3 (plus the material's sustained factor 0.5 for belt preload) | `part.py`, `materials.toml` |
| PETG: E in plane / across layers | 2000 / 1600 MPa | `materials.toml` |
| PETG: strength in plane / across layers | 40 / 20 MPa | `materials.toml` |
| Infill knockdown on stiffness / strength | 0.6 / 0.6 | `profiles/default.toml` |

With these, the effective short-term strength of a real part is 24 MPa in plane and 12 MPa
across layers, and 12 / 6 MPa under continuous load, before the safety factor of 3.
That is very conservative on purpose; the first F2 results will show whether it is useful.

## 13. F2 results (2026-11-20: done; the first real verdicts are in `fem/verdicts.toml`)

**What exists**

| Item | Where |
|------|-------|
| `python -m plotter_cad fem NAMES...` (also `make fem NAMES="..."`; `--size MM`): runs the whole pipeline, writes `fem/results/<name>/{report.md,result.json,part.json,...}`, updates `fem/verdicts.toml` (verdict, date, geometry hash, spec hash), exits 1 on FAIL or INCONCLUSIVE | `src/plotter_cad/fem/`, `build.py` |
| `python -m plotter_cad part NAME --stl PATH`: the part in its analysis frame (the runner calls it in a subprocess with `PLOTTER_FN=20`) | `part_report.py` |
| STL cleaning, gmsh meshing with fallbacks, CalculiX deck (transversely isotropic material, material axis 3 = build direction), `.frd` reader | `fem/stl.py`, `mesh.py`, `ccx.py` |
| Loads as nodal forces (force, exact couple, body acceleration), supports as constrained nodes | `fem/applied.py` |
| Failure index (in-plane and interlayer modes), displacement criteria, status thresholds (PASS up to 85 % of a limit, MARGINAL up to 100 %, FAIL beyond) | `fem/evaluate.py` |
| Runner, sanity checks, report, verdicts | `fem/runner.py`, `report.py` |
| Tests: cantilever benchmark in two layer orientations, failure index, couple distribution, cleaning, status logic, and an end-to-end run of the slider (skipped if gmsh or CalculiX are missing) | `tests/test_fem.py` |

**Validation:** the cantilever benchmark (100 × 10 × 5 mm, PETG effective values) matches the
Timoshenko closed form within **1.2 %** with the layers flat (bending uses the in-plane modulus)
and **1.0 %** with the layers along the beam (bending uses the across-layer modulus), so the
material orientation is applied correctly.

**Sanity checks on every run:** reactions balance the loads (loads that land on constrained
directions are carried by the support directly and excluded from the sum); the largest
displacement changes by at most 5 % between the two meshes (else INCONCLUSIVE); mesh volume within
2 % of the STL.

**Strength is judged away from singular spots:** nodes within 1.5 element sizes of the edge of a
loaded or supported patch are excluded. The report also states the raw peak, and how much the
peak stress changed between the two meshes (a large change suggests a sharp-corner singularity,
where a fillet would lower the real stress).

**Mesh robustness (found while running real parts):** gmsh sometimes crashes, or produces
zero-length edges that CalculiX rejects as non-positive Jacobians. The runner merges coincident
nodes and retries other gmsh settings automatically (five in turn).

**Cost:** slider ~25 s, mount ~40 s, bracket ~10 min (element size 2.2 mm; 120k-190k elements).
`fem/results/` is large (hundreds of MB for the bracket) and git-ignored; `make clean` removes it.

**Not done yet (F3):** pictures. The fine mesh and `.frd` results are kept for it.

## 14. Speed and stability round (2026-11-20)

Measured first: dropping the boundary-driven interior sizing saves only 15-20 % of the elements,
doubling the element size saves 5-6×, and CalculiX was running on one of the 8 performance cores.
Changes:

| Change | What it does |
|--------|--------------|
| **C: mesh-independent regions** (`fem/mesh.py`: `cover_region`) | Each boundary face is sampled (6 × 6 points) and a region covers the samples inside it, so the loaded or supported area no longer depends on which triangles happen to have their centroid in the region. Loads are consistent nodal forces (quadratic shape functions); supports constrain the nodes next to covered samples. This was the cause of the mount's failed convergence checks. |
| **A: cheaper runs** (`fem/solve.py`, `runner.py`) | One mesh first; a finer second mesh only if some criterion's utilization is within 0.6-1.6 (`--refine auto`; `always` and `never` exist). Load cases that are multiples of each other (peak = 1.5 × preload) are scaled, not solved again. Distinct cases run in parallel as separate CalculiX processes. (CalculiX is also given the cores through `OMP_NUM_THREADS` and `CCX_NPROC_*`, but the F test below shows this build ignores them.) |
| **B: graded mesh** (`fem/mesh.py`: `SizeField`) | gmsh box size fields around every load and support region: element size `near` (2.0-2.2 mm) inside and in a transition zone, 2.5 × that elsewhere (at most 6 mm). `--uniform` turns it off. |
| **Mesh robustness** | Coincident nodes are merged with a neighbor-cell search (the earlier rounding missed pairs split by a cell boundary) and any element with a repeated node is dropped; this removed the "nonpositive jacobian" retries. |

**Results** (same three parts, default settings, 8-core laptop):

| Part | Before | After |
|------|--------|-------|
| `x_idler_slider` | 24 s, 21k tets | 7 s |
| `x_idler_mount` | 38 s; convergence check failed (14 %) | 20 s; converged (4.3 %) |
| `gantry_end_bracket_left` | 561 s, 192k tets, 473 MB of files | **62 s, 83k tets, 68 MB**; converged (2.7 %) |

Displacements agree with the earlier runs within 2 % (bracket beam seat 0.430 mm vs 0.437 mm);
strength utilizations moved (bracket 6.4 → 4.9) because loaded and supported areas are now the
real region and not whatever triangles fell inside it.

**F: CalculiX solver test** on the bracket's 83k-element input (one load case):

| Solver | Time | Result |
|--------|------|--------|
| SPOOLES (default) | 39.6 s | reference |
| ITERATIVE CHOLESKY | 103 s | same to 5 digits |
| ITERATIVE SCALING | 327 s | same to 5 digits |
| PARDISO, PASTIX | n/a | not linked in the FreeCAD build |

The default stays. Thread count made no difference either (1 thread 41 s, 4 threads 39 s, 8
threads 40 s): the speed-up came from the smaller meshes, not from parallelism. `--solver`
remains available for experiments.

## 15. F3 results (2026-11-20: done)

`python -m plotter_cad fem NAMES --viz` (or `make fem NAMES="..." ` with `--viz` added to the
command) writes, for every load case, into `fem/results/<name>/viz/`:

| File | Shows |
|------|-------|
| `<case>_utilization.png`, `_utilization_rear.png` | The part deformed (scale printed on the image) over a faint ghost of the original, colored by **utilization** = failure index × safety factor: blue is fine, yellow starts at 85 %, orange is the allowable (1.0), red and purple are over it. A magenta ball marks the governing strength point; the top-left text lists every criterion of the case with its verdict. |
| `<case>_displacement.png` | The same shape colored by displacement magnitude in mm. |
| `<case>_hotspot.png`, `_hotspot_rear.png` | The same views zoomed on the governing strength point. |
| `<case>.vtu` | The undeformed volume mesh with displacement and utilization fields, for ParaView or FreeCAD. |

Rendering runs in FreeCAD's bundled Python (VTK, offscreen, no window), about 2-3 s per case.
`report.md` lists the pictures. A failed render is reported as a note and does not fail the check.

**What the first pictures showed:** the slider fails where the arm meets the plate next to the axle
bore, and its axle tilts upward (the couple from the belt pull above the screw). The mount's
dovetail ridge, where the slider's couple is applied, is the red area, and its surface ripples
under the linearly varying load: that is partly an artifact of how the couple is modeled (forces on
a thin ridge surface), so a ridge-top result should be read with care. The sub-agent should flag
this kind of finding instead of treating it as a design failure.

## 16. F4 results (2026-11-20: done, dry run accepted)

**What exists:** `.claude/agents/fem-analyst.md` (the sub-agent: strongest model, tools Bash,
Read, Glob, Grep, so it cannot edit anything), `docs/fem.md` (conventions, thresholds, how to
read a result), README §7.8 and the FEM bullet in §7.4, the finishing step in `CLAUDE.md`, and
the task line in `STATUS.md`. The agent type loads at session start; for the dry run a
general-purpose agent was given the definition as its instructions.

**Dry run: `x_idler_slider`.** The agent ran the check, looked at the pictures and reported:
FAIL; weak at the axle bores across the layers (delamination of the +y arm at the bore, the layers
being y-z planes because the slider prints on its back); the rear wall around the M3 hole is a
second zone; the whole slider tips about its low supports. It judged the peak partly a mesh
singularity (+9 % on the default mesh, +36 % at 1 mm), gave a sensitivity (belt preload of about
22 N per run or less would pass; interlayer strength 30 MPa gives about 1.2; both together about
0.75) and ranked suggestions (more material and fillets around the bore, thicker rear wall,
orientation with the arms along the layers). Its questions: is 40 N per run the real preload, and
is a 0.1 mm vertical limit needed for a constant static offset of the idler?

**Changes made from the agent's feedback:**

| Feedback | Change |
|----------|--------|
| `docs/fem.md` was missing (a failed command skipped writing it) | written |
| Diagnostic reruns overwrote the official result and verdict | `--no-record` (leave `fem/verdicts.toml` alone) with `--out DIR`; the definition says diagnostics use them and the official verdict is the default run's |
| Which load case to look at | the governing one is the case with the highest utilization (a sustained case can govern); stated in the definition and in `docs/fem.md` |
| Report lacked the stress and where | the strength detail line now gives the stress components in MPa with their allowables (in-plane, across the layers, interlayer shear) and the distance to the nearest load or support patch outline |
| Thresholds undocumented | listed in `docs/fem.md` (marginal 85 %, refinement band 0.6-1.6, singularity flag 25 %, sanity tolerances) |
| No rule when the peak grows with refinement | report the official verdict and the finer run as a diagnostic, and say the peak is probably a singularity |

**Not changed, for your decision:**

- The agent noted that the uniform traction over the axle bore's 60° facing region puts a stress
  step at the patch edge, which can create the hot spot it reports. A cosine-weighted bearing
  load would be more realistic. This is a change to how loads are applied (tool, F5), not to the
  spec.
- The agent suspects a stale docstring: `x_idler_slider.py` says the axle bolt's head is on the -y
  arm, but `X_TENSIONER.head_side = 1` puts the head on the +y arm (the nut on -y). I did not touch
  it (no CAD changes yet).

## 17. F5, first slice (2026-11-20)

| Item | State |
|------|-------|
| `fem-status`: every printable part with its state; verdicts flagged **STALE** when the part's properties or its cleaned STL changed since the check | done |
| Bearing load (`Force.bearing`): an axle's share on a bore wall falls off with the cosine of the face angle, so there is no pressure step at the patch edge; used on the tensioner sliders | done (the X slider's governing point did not move: 0.605 vs 0.614 × SF 3) |
| Tensioner spec shared by X and Y (`slider_fem`, `mount_fem`, `Placement`); X slider and mount rebuilt on it | done |
| `y_idler_slider_left` (right = exact mirror, `Part.mirror_of`), `y_idler_mount_left` | defined and checked: all FAIL under the harsh assumed values (slider: interlayer shear at the nut seat's lower edge, mount: tension across the layers at the end block's base), displacements within limits except the slider's vertical limit at peak (marginal) |
| `y_idler_mount_right` (chiral endstop tower), `gantry_end_bracket_right`, motor mounts, carriage, pen holder | to define; they need loads we don't have (motor and carriage mass and acceleration, pen pressure, wheel loads) and, for the mounts, a decision on how the motor's pull enters |
| Assemblies with contact, buckling, modal analysis, calibration | later |

## 18. Assumed loads for the remaining parts (accepted; implemented in §19)

Nothing here is implemented. Every value is `ASSUMED` with its basis, to be replaced by
measurements. The facts it rests on: gantry ~1.5 kg and speeds of 30-100 mm/s (README §3.1),
NEMA17 ~0.28 kg (assumed, `docs/hardware.md`), GT2 20T pulley pitch radius 6.37 mm, pen pressure
20-80 g (STATUS T3.6), servo FT90M 1.9 kg·cm at 4.8 V and a horn arm of 17 mm (`docs/hardware.md`).
The mass of printed parts at about half the solid volume (infill and walls): carriage ~60 g, pen
holder body ~13 g, pen slide ~10 g.

### Global values

| Quantity | Proposal | Basis |
|----------|----------|-------|
| Peak acceleration | 3000 mm/s² (0.3 g) | Typical firmware cap for a light plotter; also the highest the pen allows. Needs the Marlin value (T2.2) |
| Drive force | Y belt: gantry 1.5 kg (it includes the X motor) × 3 m/s² / 2 belts = 2.3 N each. X belt: carriage with pen head ~0.3 kg × 3 m/s² = 0.9 N | m × a |
| Stalled-motor torque | **0.4 N·m** (NEMA17 holding torque) | Common NEMA17 value; **please read the label of the motor on hand** |
| Peak belt-run tension | **preload 40 N + stall share 31 N = 71 N** | A jammed gantry makes the driven run carry up to torque / pulley radius = 63 N more than the other; each run gets half of it. This replaces the arbitrary "+20 N dynamic" used so far (60 N per run), which is well above the real drive forces (2 N) but below the jam case. It would make the existing peak cases about 18 % heavier |
| Motor mass | 0.28 kg (2.7 N) | `docs/hardware.md`, assumed |
| Pen knock | 20 N sideways at the pen tip, short (not sustained) | A hand or a curled sheet hitting the pen; no measurement basis, the number is a judgment |
| Servo stall | 11 N at the horn tip | 1.9 kg·cm = 0.186 N·m / 17 mm; at 5 V a little more |
| Weights | Carriage with pen head ~0.25 kg (2.5 N down) | printed parts above + 4 wheels + servo + pen |

### Per part

| Part | Load cases | Supports | Limits |
|------|-----------|----------|--------|
| `x_motor_mount`, `y_motor_mount_left/right` | belt radial pull 2 × T (preload sustained, jam peak) along the belt toward the idler, spread on the plate's motor screw seats; motor weight; the stall torque as a couple on the same seats | the mount's foot screws or bracket bolts (as the idler mounts) | 0.1 mm perpendicular to the belt, 0.3 mm along it, at the motor face |
| `gantry_end_bracket_right` | as the left bracket, with the motor mount's footprint, its radial pull and the stall couple in place of the idler's | the 8 block bolts | beam seat 0.1 mm per axis |
| `y_idler_mount_right` | as the left mount (belt only) | wood screws and the foot on the baseboard | as the left mount |
| `x_carriage` | (1) X belt: the two clamps pull the rear block apart, ±T along x (preload, peak 71 N); (2) weight and acceleration of the carriage and head; (3) pen knock through the tool-plate hook and screws. The wheel preload is internal (top and bottom wheels squeeze the beam) and stays a hand check | the wheel axle bores, fixed | tool plate 0.05 mm per axis under cases (1) and (2) (the pen position), strength only under the knock |
| `pen_slide`, `pen_holder_body` | (1) pen pressure 0.8 N along the pen axis plus drag 0.4 N; (2) servo stall 11 N on the slot ceiling; (3) pen knock 20 N at the pen tip | the rod sleeves, the key rib, then the rod seats in the holder body; the holder body on the tool plate hook and 2 × M3 | pen axis 0.05 mm under (1), strength only under (2) and (3) |

### Decisions I need from you

1. **Motor holding torque** (label of the NEMA17 on hand). 0.4 N·m is a guess.
2. **Peak belt tension:** keep 60 N per run, or switch to preload + the jam share (71 N with 0.4 N·m)?
3. **Pen knock 20 N:** keep, change, or drop (it governs the carriage and pen holder, because the lever arm is large)?
4. **Acceleration:** 3000 mm/s² unless the Marlin configuration says otherwise.
5. **Strength-only cases:** I propose no displacement limits on the abuse cases (stall, knock), only strength, with the same safety factor. OK?

## 19. F5, second slice: the remaining parts (2026-11-20)

All the parts of §18 are defined with the accepted values; the motor torque is still the guessed
0.4 N·m (no label read yet) and the peak belt tension is now preload + the jam share = 71.4 N.

**What changed in the tool:** `loads.py` holds the accepted values (acceleration, masses, stall
torque, jam share, knock, servo stall, pen pressure) and `lever_couple`; `parts/motor_fem.py`
builds the motor's loads (radial pull moved from the pulley to the seat with its lever couple,
weight, and at a jam the stall torque) for the motor mounts and for the right bracket; both
brackets now carry the lever couple of the belt pull that acts above the base (the left bracket's
earlier loads left it out, which overstated the moment); `FemSpec.default_displacement_limit_mm =
None` makes a part strength-only; load cases can be named in a displacement limit's
`load_cases` so that abuse cases (knocks, stall) only get a strength check; a run keeps going when
one part cannot be checked (reported as INCONCLUSIVE); the STL cleaner now splits a triangle at a
T-junction where it drops a zero-area triangle (the pen slide could not be meshed without it).

**Results** (harsh assumed values: SF 3, sustained × 0.5, infill × 0.6; utilization 1.0 is the
allowable; all sanity checks pass):

| Part | Verdict | Worst strength | Worst displacement over its limit |
|------|---------|----------------|-----------------------------------|
| `x_idler_slider` | FAIL | 1.82 (belt_preload) | idler_axle_vertical 0.2035 of 0.1 mm (belt_peak) |
| `x_idler_mount` | FAIL | 9.34 (belt_preload) | idler_seat_vertical 0.2746 of 0.1 mm (belt_peak) |
| `y_idler_slider_left` | FAIL | 1.91 (belt_preload) | idler_axle_vertical 0.1092 of 0.1 mm (belt_peak) |
| `y_idler_mount_left` | FAIL | 2.15 (belt_preload) | none over |
| `y_idler_mount_right` | FAIL | 2.16 (belt_preload) | none over |
| `x_motor_mount` | FAIL | 4.65 (belt_preload) | motor_face_sideways 2.0727 of 0.1 mm (belt_peak) |
| `y_motor_mount_left` | FAIL | 4.12 (belt_preload) | motor_face_sideways 0.964 of 0.1 mm (belt_peak) |
| `gantry_end_bracket_left` | FAIL | 4.41 (belt_preload) | beam_seat_x 0.6958 of 0.1 mm (belt_peak) |
| `gantry_end_bracket_right` | FAIL | 4.94 (belt_preload) | beam_seat_x 0.7833 of 0.1 mm (belt_peak) |
| `x_carriage` | PASS | 0.58 (pen_knock_y) | none over |
| `pen_slide` | PASS | 0.22 (pen_knock_d) | none over |
| `pen_holder_body` | MARGINAL | 0.95 (pen_knock_x) | none over |

**What stands out**

- The **X idler mount** is by far the weakest (9.3): tension across the layers at the foot of the
  thin end block, where the screw head pushes with the full idler force.
- The **motor mounts** twist: the belt pulls 18-25 mm in front of the plate, so the couple bends
  the 5 mm plate out of plane and the motor face moves **1.2 mm (X, preload) and 0.55 mm (Y)**
  perpendicular to the plate against a 0.1 mm limit. This is the largest functional concern in
  the set (motor tilt, pulley and belt alignment).
- The **brackets** deflect 0.4-0.8 mm along the beam axis at the beam seat (limit 0.1 mm).
- The **carriage** (belt clamps, weight, knocks) and the **pen slide** pass with margin; the **pen
  holder body** is marginal under a sideways knock: the lower arm's rod seat carries 1.5 × the
  knock, and the body prints on its side, so a knock along x pulls across the layers.
- Strength is dominated by interlayer tension in nearly every part, which is a statement about
  print orientation as much as about geometry.

Not yet modeled: the wheel preload (internal to the carriage), contact and friction, and the
foot-to-bracket friction of the idler and motor mounts.

## 20. Remodeled bracket seat and mount feet (2026-11-20)

Two modeling changes agreed after the walk-through of the X idler mount findings:

1. **Brackets: the beam holds the face plate's seat.** The beam's push-back used to be a load on
   the pocket floor, so the face plate leaned like a free cantilever (0.4-0.8 mm). The beam is stiff
   (and both ends are pulled equally), so the pocket floor is now a support in x and the mount's
   pull is the only belt load on the bracket. The limit that matters moved with it: how far the
   **mount's foot moves** (relative to the held seat) slackens the belt, so the limits are now on
   the foot's footprint (0.1 mm per axis) and on the seat in y and z (the beam end's height and
   alignment).
2. **Mount feet: friction zones.** The underside of each mount's foot within 8 mm of a clamping
   screw (`regions.bond_zone`, `BOND_RADIUS`, about twice the head diameter) is bonded to what it
   is clamped on (all four mounts: rear bolts, front bolts, wood screws); the rest of the foot still
   rests there and holds z only.

**Effect** (preload, before to after; utilization / displacement in mm):

| Part | Strength | Notable displacement |
|------|----------|----------------------|
| `gantry_end_bracket_left` | 4.41 to 0.37 (marginal only because a raw peak at a support edge exceeds the limit) | foot x 0.011, z 0.058 (0.103 at peak: over its limit); seat y 0.006, z 0.003; verdict FAIL only for that peak |
| `gantry_end_bracket_right` | 4.94 to 0.22 | foot 0.004 / 0.002 / 0.006; **PASS** |
| `x_idler_mount` | 9.34 to 9.32 | along belt 0.362 to 0.329, sideways 0.138 to 0.095 (marginal), vertical 0.154 |
| `x_motor_mount` | 4.65 to 4.65 | sideways (plate bending) 1.169 unchanged |
| `y_idler_mount_left/right` | 2.15 to 2.16 | unchanged, within limits |
| `y_motor_mount_left` | 4.12 to 4.12 | sideways 0.553 unchanged |

So the brackets are not a problem once the beam is modeled as stiff; the friction zones help only the
mount's sideways and along-belt displacement; the strength failures of the mounts (the thin X end
block, the motor plates) are untouched, which confirms they are real features of those parts and not
of how they are held.

## 21. X idler mount: options for the end block (2026-11-20, FEM only; no CAD changed)

Variants were built as scratch geometry (the real mount plus added solids) and run on one coarse
mesh each (preload, utilization; baseline 9.24 on the same mesh; treat differences under about
25 % as noise).

| Option | Utilization | Along belt (mm) | What governs |
|--------|-------------|-----------------|--------------|
| Baseline | 9.24 | 0.32 | block base corner, 16.6 MPa across the layers; the foot's underside at the bracket's base edge, 29-37 MPa in plane |
| Block 3 mm thicker (outboard, 8 mm) | 8.89 | 0.26 | the foot overhang, 35.6 MPa in plane |
| Block 5 mm thicker (10 mm) | 8.35 | 0.26 | the same |
| Two gussets, 8 mm long, 3 mm thick | 8.50 | 0.30 | the same |
| Printed on its side (layers normal to y) | 7.19 | 0.30 | mixed |
| **Support under the overhang** (bracket base 10 mm longer outboard; the mount unchanged) | **3.36** | **0.21** | the ridge flank under the slider, 3.0 MPa across the layers, partly an artifact of the couple model |
| Support under the overhang + gussets | 4.31 | 0.18 | the ridge flank |
| Support under the overhang + 8 mm block | 5.76 | 0.13 | the block base corner (not understood: a thicker block should not be worse; treat thickening as inconclusive) |
| Support under the overhang + printed on its side | 4.71 | 0.20 | mixed |

**Reading.** The mount hangs 4-9 mm past the outboard edge of the bracket's base with nothing under
it, and the force that the screw head puts on the block bends that overhang. Making the block
thicker or adding gussets does little while the overhang governs; carrying the overhang on the
bracket cuts the worst value to about a third and the along-belt displacement by a third, with no
change to the mount. The earlier hand estimate of 9.2 MPa across the layers at the block base
assumed the foot top as its base; the dovetail ridge stiffens the lower part, so the block's own
bending stress is closer to 5 MPa, and the FEM no longer shows it as the weak point once the
overhang is supported.

**Proposal (needs the CAD owner's check):** lengthen the left bracket's base outboard by about 10 mm
under the mount (`BRACKET.x_out` -38 to about -48 over the mount's y range only, or whole), after
checking the Y belt clamp (belt line x = -30), the endstop trigger boss and the loom anchor on
the right bracket; then re-run the mount, the bracket and the slider. The mount's block can then be
revisited if the check still shows it.

## 22. Shelf under the X idler mount: built and re-checked (2026-11-21)

`BRACKET.shelf_x` = −48 (left bracket only, over the mount's footprint y 16…62.5, same thickness,
flat underside): bracket 68 × 125 mm, +4.7 cm³; STLs and inspect renders regenerated; `make check`
and `make test` pass (334 tests; one design check added). Clearances in the whole-machine assembly
at the front, middle and back of the gantry's travel: no overlap, nearest part the Y belt at about
5 mm, endstop keep-outs clear.

**FEM, before to after (preload, utilization / mm):**

| Part | Strength | Along belt | Sideways | Vertical |
|------|----------|------------|----------|----------|
| `x_idler_mount` | 9.32 to **4.34** (peak 8.32 to 3.87) | 0.329 to **0.221 (PASS)** | 0.095 to 0.096 (marginal) | 0.154 to 0.151 |
| `x_idler_slider` | 1.82, unchanged | unchanged | unchanged | 0.114, unchanged |
| `gantry_end_bracket_left` | 0.37 to 0.51 | foot x 0.011 to 0.017 | foot y 0.005 to 0.008 | foot z 0.058 to **0.120 (FAIL)** (peak 0.214) |

The mount's worst value halves (the earlier scratch variant predicted a third; the real geometry
also changes the mesh) and its along-belt movement now passes. It still fails: the block base and the
ridge flank under the slider are at about 4.3 against the harsh allowable, and the vertical movement
is 0.15 mm.

**Bracket foot z is a modeling question, not a design one.** The mount's couple (belt pull above the
base) is applied on the bracket's footprint as linearly varying vertical forces, which pull up on
the shelf's outboard end; a contact can only push, and in the real joint the couple is carried by
the bolt clamp. A diagnostic run without the couple (not recorded) gives: strength 0.23 (peak 0.20),
foot z 0.021 (0.037 at peak), foot x 0.007, **everything PASS**. The recorded verdict keeps the
couple and so reads FAIL until this is decided.

## 23. Bracket footprint without the mount's couples (2026-11-21)

The couples of the mount's pull (the belt pull acts above the base; for the motor mount also the
stall torque) are no longer applied on the brackets' footprints: the clamped joint carries them
through its bolt preload, and a linear distribution would pull up on a surface that can only be
pushed. The footprint carries the force and the motor's weight (`motor_loads(..., couples=False)`).
The mounts' own checks still include the couples (they are the part loaded by them).

| Part | Before (with couple) | After |
|------|----------------------|-------|
| `gantry_end_bracket_left` | FAIL: foot z 0.120 (preload), 0.214 (peak); strength 0.51 | **PASS**: strength 0.23 (peak 0.20), foot x 0.007, z 0.021 (0.037 at peak) |
| `gantry_end_bracket_right` | PASS, strength 0.22 | **PASS**, strength 0.22 (peak 0.20), foot z 0.002 |

So with the shelf the left bracket passes, as the right one does. What remains open in this area is
the X idler mount itself (strength 4.3, vertical movement 0.15 mm) and the slider (1.8).

## 24. Assembly check: the tensioner's tilt (2026-11-21)

**Observation (user, on a printed X idler):** with the belt tight the idler leans: the belt pulls
the axle, which sits above the tension screw, and the mount "allows the flexibility".

**What the part checks saw:** nothing of it. The slider is checked with its dovetail held
rigid and the mount with the slider's couple on the ridge, each against 0.1 mm; the clearance has
no stiffness, and the deflections were never added.

**New:** `Assembly` (part.py), `ASSEMBLY_CHECKS` (assembly_checks.py), `fem/assembly.py`. Terms for
the idler axle: slider's own flex + mount's own flex + rigid tilt of the slider in its dovetail
(`tension_idler.dovetail_play`: roof clearance + flank clearance × √2 over the plate length,
pivoting about the plate's front end). Limit: the members' limits added (0.2 mm vertical and
sideways, 0.6 mm along the belt); nothing new is decided.

**Result on the current design (belt_preload / belt_peak):**

| Tensioner | Vertical | Along belt | Verdict |
|---|---|---|---|
| X (plate 10.4 mm long, axle 14.5 mm above the screw) | 0.55 / 0.76 mm, 2.8× / 3.8× the 0.2 limit; play alone 0.29 | 1.25 / 1.55 mm (0.86 from play) | FAIL |
| Y left and right (plate 23 mm) | 0.24 / 0.32 mm | 0.58 / 0.75 mm | FAIL (vertical), along belt MARGINAL / FAIL |

The shelf (T3.19) does not touch the dovetail, so it does not address this: the clearance term
is 0.29 mm vertical on the X tensioner whatever the foot does. Fix options are in STATUS.md.

## 25. Floating X idler: tower in the bracket (2026-11-21)

Decision (user): the screw in line with the axle (no couple, so no rail), the idler mount merged
into the left bracket (STATUS.md T3.22). The screw's tip needs a tunnel in the slider's wall
(option A: head-driven, hex key from outside), which makes the slider 10 mm longer and the tower
20 mm further out than the old block.

**Spike (scratch bracket with a tower, preload):** 8 mm tower plate, no gusset: strength 5.8, seat
x 1.5 mm; 16 mm plate with a 10 mm gusset: strength 1.1. The weak spot is the tower root in
tension across the layers, so thickness helps more than gussets.

**Built and iterated (left bracket, belt preload):**

| Variant | Strength (limit 1) | Tower seat vertical (limit 0.1) |
|---|---|---|
| 6 mm plate, walls only to the bracket's edge | 6.7 | 0.40 mm |
| 6 mm plate, walls 6 mm to x = −22 | 2.75 | 0.099 |
| 10 mm plate, 7 mm washer | 1.58 | 0.094 |
| 12 mm plate, 9 mm washer, 6 mm walls | 0.88 | 0.100 |
| + 8 mm walls | 1.07 (hole's teardrop apex) | 0.088 |
| + round hole (final) | 0.69 | 0.085 |

Final: peak seat vertical 0.152 mm (own limit 0.1: the bracket check fails on it), everything else
passes. The slider (printed on its side, so the pull runs along the layers): strength 0.46, axle
moves 0.04 / 0.02 / 0.02 mm (along / sideways / vertical). **X assembly check: MARGINAL**
(vertical 0.108 mm at preload, 0.192 at peak, limit 0.2).

Modeling notes: the slider is held by the screw in its hole and tunnel (y, z), the nut seat (x) and
one outer face standing for a wall (roll); the bracket's tower seat is the screw hole's wall (the
plate's corners would count its rotation twice). A lesson for the mesher: the tower's coplanar
faces with the shelf left a 0.01 mm sliver unless the tower is sunk 1 mm into the base, and a
horizontal hole needs a teardrop or round hole with a clean surface (gmsh failed on a slivered
tower).

## 26. Floating Y idlers (2026-11-21)

The Y idler mounts get the same floating idler (STATUS.md T3.23) since the Y dovetail
tensioners failed the assembly check (vertical 0.21 / 0.29 mm against 0.2 at preload / peak).
One generic implementation (`parts/floating_idler.py`: slider, tower, FEM regions and specs) serves
both ends; `params.FloatingIdler` holds the dimensions, `X_IDLER` and `Y_IDLER` place it.

**Result (preload / peak):**

| Part | Strength (limit 1) | Tower seat (mm: along / across / vertical) | Verdict |
|---|---|---|---|
| Y idler mount (left = right) | 0.45 / 0.40 | 0.06 / 0.01 / 0.02 | PASS |
| Y idler slider | 0.50 / 0.44 | axle 0.04 / 0.01 / 0.02 | MARGINAL |
| Y assemblies (left, right) | | vertical total 0.03 mm of 0.2 | PASS |
| X bracket (11.4 mm plate) | 0.67 / 0.60 | 0.09 / 0.02 / 0.08 (0.147 at peak) | FAIL (own vertical limit at peak) |

The Y mount's tower stands on the foot, which is screwed to the baseboard right beside it, so the
load path is short and stiff (the X tower hangs 20 mm off the bracket's edge). The tower plate of
both is 11.4 mm: the screw's length quantizes to M3×25 up to that thickness and to M3×30 above it.
