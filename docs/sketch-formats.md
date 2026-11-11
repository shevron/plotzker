# Parametric 2D sketch formats (research for D23; outcome: D24)

**Outcome (D24):** stay with SVG; designers export solved sketches from their CAD tool. The
Python constraint-sketch trial (bottom) was rejected and its code removed. Future option:
automate FreeCAD export (option E/F below).

Question: SVG sketches (D23) give us a drawn profile but no parametric intent. Is there a
better format, or a better way to use SVG, so that a sketch is *a few input values plus
constraints* (FreeCAD-Sketcher style) and PythonSCAD extrudes the solved result?

## What D23 does today

`geometry.load_sketch()` → `osimport(svg)`: filled outlines, y flipped, curves faceted.
Dimensions live only in a comment; changing one means redrawing. No constraints, no
named parameters, no link to `params.py`.

## Findings

1. **No open, widely supported *interchange* format carries sketch constraints.**
   - SVG, DXF, PDF: geometry only. Exporting a FreeCAD sketch to DXF/SVG drops every
     constraint (forum/tracker reports also show broken exports of circles and open paths).
   - STEP AP203/214/242 exchange solids; the constraint extension (ISO 10303-108) is
     essentially unimplemented by CAD tools. Not a real option.
   - Each CAD keeps constraints in its own native format: FreeCAD `.FCStd` (a zip
     with `Document.xml`; sketch geometry, constraints and expressions are XML, but the
     schema is internal and changes between releases), SolveSpace `.slvs` (text
     `key=value` records, implemented in `file.cpp`, not formally documented),
     Fusion/Onshape/SolidWorks (proprietary).
2. **A sketch is really *data + a solver*.** The portable part is the constraint
   solver, which exists as embeddable libraries:

   | Solver | Python binding | Notes |
   |---|---|---|
   | SolveSpace (GPL-3) | `python-solvespace` 3.0.8 | **Tested here:** builds on Python 3.14/macOS arm64 from sdist; a constrained rectangle solved correctly and reported DOF |
   | FreeCAD PlaneGCS (LGPL) | `planegcs` | Same constraint set as FreeCAD Sketcher (tangent, symmetric, arcs, ellipses, B-splines, `diagnose()`); **failed to build here** on 3.13 and 3.14 (CMake error, no macOS wheel) |
   | SolveSpace / PlaneGCS in other stacks | CadQuery's `Sketch` solver, build123d | Tied to OpenCascade; we use PythonSCAD |

3. **The constraint set is small and the same everywhere** (coincident, horizontal/vertical,
   parallel/perpendicular, equal, tangent, point-on-curve, symmetric, distance, radius,
   angle). Writing our own format over a solver means no vendor lock-in.

## Options

| # | Approach | Parametric | FreeCAD interop | Effort | Verdict |
|---|---|---|---|---|---|
| A | Keep SVG as is | No | Import/export geometry only | none | Fine for fixed vendor shapes; fails the stated goal |
| B | **Python sketch DSL on a solver** (points/lines/arcs + constraints + named dims taken from `params.py`; solved with python-solvespace, then `polygon`/arc discretization → PythonSCAD) | Yes, fully, and ties to `params.py` | None directly; sketches are code (but are readable, diffable) | Medium | **Recommended** |
| C | SVG + constraint metadata (own `xmlns`/`data-*` attributes, solver re-positions elements, writes SVG) | Yes | Inkscape ignores/keeps the attributes but cannot edit constraints | Medium-high; we invent a format *and* lack an editor | Worse than B |
| D | SolveSpace `.slvs` as source, headless export | Yes, with SolveSpace GUI as the interactive editor | Not FreeCAD; SolveSpace imports/exports DXF | Medium; need a parser or the CLI to solve and export | Best if a **GUI** sketch editor is the priority |
| E | FreeCAD `.FCStd` as source; read `Document.xml` or run `FreeCADCmd` headless to export solved outlines | Yes, with the real FreeCAD Sketcher GUI | Native | High: FreeCAD (large) becomes a build dependency; internal schema changes by release; breaks the “PythonSCAD is the only source” rule (D2/D22) unless relaxed | Only if you insist on FreeCAD |
| F | Parametric-in-FreeCAD, then export solved DXF/SVG as a *generated* artifact checked in | Parametric only inside FreeCAD; the repo holds the output | Native, one-way | Low | Pragmatic, but the output is the same dumb SVG; constraints live outside the repo |

## Recommendation

**B as the default, with D as the optional GUI route.**

- B satisfies the intent literally: a handful of named inputs (some from `params.py`,
  e.g. `BEAM.slot_width`), everything else solved from constraints, deterministic and
  testable (the solved sketch can be checked for DOF = 0 / no conflicts, which fits the
  project's `design_checks()` philosophy).
- The V-slot profiles are a good first target: the notes at the top of the SVGs
  (lip 1.85, 45° chamfers, 12 mm cavity, 1.4 mm webs) are already constraints in prose.
- Keep SVG (A) for shapes that really are fixed free-form outlines.
- If you want to *draw* constrained sketches interactively rather than write them,
  SolveSpace (D) is the lightest open tool that does it; FreeCAD (E) only if you
  already prefer its GUI.

Licensing caveat: `python-solvespace` is GPL-3. That is fine for a personal CAD
repo, but note it if the project is ever published under another license.

## Open items before adopting (needs your decision; do not change D23 yet)

- B vs D (code-first vs GUI-first)? This changes D23 and the “SVG sketches” rule in `CLAUDE.md`.
- Add `python-solvespace` to `pyproject.toml` (source build needs a C++ toolchain/CMake;
  check `uv sync` on your machine).
- Proposed spike if B: `plotter_cad/sketch.py` (~150 lines: `Sketch`, `point/line/arc`,
  constraint helpers, `to_pythonscad()`), port `vslot_2020` and compare the area against the
  SVG-derived areas recorded in `hardware/vslot.py`.

Sources and confidence: PlaneGCS API and SolveSpace record format were read from the
`planegcs` docs and `file.cpp`; the python-solvespace result and the planegcs build
failure were run here. The FCStd structure and the lack of constraints in DXF/SVG/STEP
come from general knowledge and forum/tracker reports (the FreeCAD wiki was not
reachable), so verify before relying on them.

## Trial: option B, 2020 profile (rejected, code removed)

Built as `sketch.py`, `hardware/vslot_param.py` and `tests/test_sketch.py` on python-solvespace;
removed again, since it gives no GUI drawing and little over plain PythonSCAD.

- `plotter_cad.sketch.Sketch` (~170 lines): points, lines, constraints, `solve()`
  (reports conflicts and leftover degrees of freedom), `to_2d()` → PythonSCAD.
- `VSlotProfileSpec` holds 7 inputs (size, opening, lip, cavity, wall/floor depth, bore);
  the neck width (6.2) and floor width (5.8) are `@property`s that fall out of the 45°
  constraints. One slot is written once and applied to all four faces, each seeded from
  a rough hand-typed shape.
- Result: DOF 0, 44 outline points; coordinates equal the SVG's (5.05, 6.9, 4, 3, 7.1,
  6.1, ...) and the net area is 161 mm², as in the SVG. Changing e.g. `lip` or `cavity`
  re-solves cleanly.

Things learned:

- SolveSpace's point-to-line distance is **signed** (positive = right of the directed
  line); `Sketch.offset()` wraps it so positive means left. Angles are unsigned, so
  seeds must be roughly right or the solver may pick the mirrored solution (this
  flipped the first attempt inside out; there is no error, the shape is just wrong).
- PythonSCAD's `polygon()` accepts lists of points but not tuples.
- Failures are not very informative: a bad constraint set returns `DIDNT_CONVERGE` and
  a list of constraint indexes, not names. Building the sketch up in stages while
  checking `solve()` / `dof` is the practical way to debug it.
- The constraints read naturally as design intent, but a 4-slot profile is ~80 lines of
  setup. There is no visual feedback loop; you cannot see the sketch while writing it.
