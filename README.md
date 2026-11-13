# DIY Pen Plotter

A 2D CNC pen plotter built mostly from parts salvaged from low-end 3D printers, standard
hardware (metric hex fasteners, bearings) and 3D-printed parts. It draws with ordinary
household pens on paper, card, cardboard or thin wood.

This file holds what rarely changes: goals, requirements, the high-level design and its
rationale, the repository layout, and the coding standards and contribution guidelines for
humans and AI agents alike.

| File | Purpose |
|------|---------|
| `README.md` (this file) | Overview, goals, high-level design and decisions, standards, contribution guidelines |
| [`STATUS.md`](STATUS.md) | Ongoing work: current status, work plan, open questions, detailed decisions, inventory, key numbers, as-built design notes, ideas |
| [`CLAUDE.md`](CLAUDE.md) | Instructions specific to AI agents; points to the two files above |
| [`docs/`](docs) | Longer research and reference: [`controller.md`](docs/controller.md) (board, pin map, firmware plan), [`hardware.md`](docs/hardware.md) (vendor part dimensions for CAD), [`sketch-formats.md`](docs/sketch-formats.md) (2D sketch format research) |

**Contents:** 1 Goals · 2 Requirements and constraints · 3 Design · 4 Design decisions ·
5 Repository layout · 6 Development setup and workflow · 7 Contribution guidelines and
coding standards

---

## 1. Goals

- A reliable, accurate pen plotter for **A3 (297 × 420 mm) and smaller** media up to
  **15 mm** thick, built from parts on hand and common 3D-printer components.
- **Modular tool head**, so the pen holder can evolve (pen-lift experiments, automatic pen
  changing, other tools) without redesigning the machine.
- **Parametric, reproducible CAD** in Python: every printed part regenerates from shared
  parameters, and design rules fail the build when a requirement is broken.
- **Easy to build, debug and service** with hand tools.

Non-goals (for now): cutting, engraving, lasers, high-speed operation, enclosure.

Build phases, the work plan and the current status are in [`STATUS.md`](STATUS.md).

---

## 2. Requirements and constraints

| # | Requirement | Notes |
|---|-------------|-------|
| R1 | Move a pen in X/Y over a **flat** work surface | Paper is the primary medium |
| R2 | Support media **0–15 mm** thick | Paper (~0.1 mm) up to cardboard / thin wood |
| R3 | **Work area: A3 (297 × 420 mm) and smaller** | Travel ≥ 320 × 440 mm for margins and registration |
| R4 | Lift and lower the pen under program control | Required in v1; without it every path is connected |
| R5 | Hold standard pens of **7–16 mm** diameter | Manual pen insertion in v1 |
| R6 | Constant, gentle pen pressure despite small height errors | Pen head absorbs ±1.5 mm (§3.8) |
| R7 | Modular, easily replaceable tool head | Path to automatic pen changing, other tools later |
| R8 | Use parts on hand wherever possible; otherwise commonly available parts | Inventory: `STATUS.md` |
| R9 | Open-source firmware and toolchain | Marlin; no custom firmware |

**Project constraints (hard rules, detailed in §7.1):**
- All measurements **metric**.
- Hardware is off-the-shelf (metric hex fasteners etc.) or common low-end 3D-printer
  parts (steppers, belts, lead screws, bearings, extrusions), plus 3D-printed parts.
- CAD in **PythonSCAD** (Python package `plotter_cad`), parametric (D2).
- Safety: printer heaters disabled in firmware and left unconnected; mains wiring
  enclosed and earthed.

---

## 3. Design

### 3.1 Kinematics: Cartesian, not CoreXY (D5)

**Where CoreXY wins:** both motors are fixed to the frame, so the moving mass is only the
carriage. That allows high acceleration and keeps motor cables static. It matters in a
3D printer, which prints fast with a relatively heavy hotend.

**Why that benefit is small for a pen plotter:**
- Plotting speed is limited by the pen, not the machine. Most pens lay a clean line at
  roughly 30–100 mm/s.
- The tool head is light (a pen plus a small servo).
- In a Cartesian gantry the only extra moving mass is the X motor (~0.3 kg), which
  NEMA17s handle easily at plotter accelerations.

**What CoreXY costs:** long belt loops with many idlers, more printed mounts and more
places to lose tension; belt-tension mismatch shows up as skewed drawings and is hard to
diagnose; it needs a rigid, square frame to carry the belt loops, whereas our Y rails are
two independent shafts on end supports; and it's harder to build, debug and modify.

**Cartesian:** each axis is independent (one motor ↔ one direction), simple to debug and
calibrate, and maps directly onto the parts we have.

Also considered: *H-bot* (racking torque on the gantry; rejected), *polargraph*
(vertical surface, low precision; rejected), *moving bed* (needs ~2× footprint; rejected).

### 3.2 Axis layout (D6, D7, D12, D13)

```
   SK10 ┃═══════════ Ø10 shaft (Y1), 700 mm ═══════════┃ SK10
              [SCS][SCS]  ← gantry end (2 blocks)
                  │
                  ├──── 4020 gantry beam (X), 520 mm ─────┐
                  │      [carriage + tool plate]          │
                  │             ↓ pen                     │
              [SCS][SCS]                                  │
   SK10 ┃═══════════ Ø10 shaft (Y2), 700 mm ═══════════┃ SK10
              steel bed on adjustable panel, on plywood baseboard
```

- **Y axis:** two Ø10 × 700 mm hardened shafts, each held at its ends by SK10 supports
  and carrying **two SCS10UU blocks**, spaced ~80–100 mm center to center for resistance
  to tilting and twisting.
- **X axis:** a **520 mm 4020 V-slot beam, mounted upright** (40 mm tall), bolted to
  gantry end brackets on top of the SCS blocks. A printed carriage rides on it on POM
  V-wheels. The beam end sits directly over the shaft, so the gantry weight bears straight
  down on the blocks; this sets the shaft spacing to **520 mm**.
- **Drive:** GT2 belts on both axes. Typical setup: 20T pulley, 1.8° motor, 1/16
  microstepping → **80 steps/mm**. Each Y side has its own belt outboard of its shaft
  (motor at one end, idler at the other; the top run is cut and both ends clamp under the
  gantry end bracket). The X belt is a vertical loop behind the beam, its top run cut and
  clamped under the carriage's rear block. The X motor sits at one beam end and the idler
  with its belt tensioner at the other. Lead screws only for an optional pen-Z experiment.
- **Gantry drive:** a motor on each Y side (second motor on the ZRIB's E0 driver,
  `Y_DUAL_STEPPER_DRIVERS`) and **one endstop per side** (`Y_DUAL_ENDSTOPS`), so the
  gantry is re-squared at every homing. Essential with closed linear bushings, which
  bind if the gantry is pushed from one end.

**Why 4020 over 2020 for the X beam:**

| | 2020 | 4020 (upright) |
|--|------|----------------|
| Mass (520 mm) | ~0.23 kg | ~0.42 kg |
| Vertical bending stiffness | baseline | ~6–8× higher |
| Resistance to twisting from the offset pen | low | much better (wheels 40 mm apart vertically) |
| Carriage | 3–4 wheel plate | Wheels on top and bottom grooves |

The pen hangs off the front of the carriage, so beam twist tilts the pen and shows as
wobbly lines. The extra 0.2 kg adds only ~0.07 mm of shaft sag.

**Shaft sag:** the closed SCS blocks run over the whole shaft, so it can only be supported
at its ends. Estimated mid-span sag (span ~680 mm, gantry ~1.5 kg → ~0.7 kg per shaft):

| Load case | Simply supported (worst) | Fully clamped (best) |
|-----------|--------------------------|----------------------|
| Shaft's own weight | 0.16 mm | ~0.03 mm |
| Gantry at mid-span | ~0.43 mm | ~0.11 mm |
| **Total** | **~0.6 mm** | **~0.15 mm** |

SK10 clamps sit in between: expect **0.2–0.4 mm**. The pen head absorbs it (§3.8).
**Keep the gantry light.** If sag ever shows up, supported rails (e.g. SBR12) can
replace the shafts on the same layout.

**Shaft alignment:** closed bushings jam when the shafts aren't parallel. Fix one shaft;
mount the second with slightly oversized SK10 holes; move the gantry to each end and
tighten the supports there, so the gantry aligns the shafts itself.

**Belt alignment (D26):** each Y motor and idler mount has a pocket for its SK10, so the
belt line follows the shaft instead of the baseboard drilling. Fit the SK10s and shafts
first (aligning rail 2 with the gantry as above), move the gantry out of the way, then
slide each mount along the shaft axis onto its SK10 and push it into the pocket's corner (end
wall against the SK10's outer face, side wall against its outboard edge; the other two sides
are open, so SK10 width and chamfer tolerances don't matter) and screw it down; the wood screws go straight through the foot
holes, with no pre-drilled positions. The Y endstop (on the idler mount) then sits at a
fixed distance from the gantry's hard stop.

**Height stack-up:** measured from the shaft mounting surface: shaft center → SCS10UU
base → SCS10UU top face → gantry end brackets → beam. The beam bottom must clear the bed,
15 mm media, a safety gap and the carriage's bottom wheels, which hang below the beam, so
the end brackets lift the beam well above the SCS top face. The stack-up is computed and
checked in `params.py`; the numbers are in `STATUS.md` and `docs/hardware.md`.

**Work area:** A3's short side (297 mm) runs across X, the long side (420 mm) along Y.
- **X travel** is the beam length minus the carriage and an end keep-out at each side
  (in front of the beam the tool head can't pass over the SCS blocks): about 426 mm.
- **Y travel** is the shaft length minus the SK10 supports and the gantry end: about
  540 mm. It covers A3 with room to park the gantry off the sheet while loading.
- Shaft spacing 520 mm center to center. Y travel is parametric in CAD.

### 3.3 Pen lift and media thickness (D14, D18)

**Approach: choose the pen-lift mechanism by experiment.** The v1 pen holder (§3.4) has a
vertical slide whose lift actuator can be swapped. Candidates are compared on real plots.

**Requirements every candidate must meet:**
- **Constant, adjustable pen pressure**: starting point ~20–80 g at the tip (fineliners
  need less, markers more), independent of media thickness and small height errors.
- **≥ 3 mm of float** below first contact with near-constant pressure, to absorb ±1.5 mm
  of shaft sag, bed and media unevenness (§3.8).
- **Lift stroke ≥ 5 mm**, so the pen clears warped media while traveling.
- **Smooth, low-friction vertical slide** with no lateral play (e.g. 2 × LM6UU/LM8UU on
  rods, or a printed slide with PTFE/brass bushings).
- **Fast, repeatable up/down** (aim < 100 ms), with no bounce or drag marks on touchdown.
- **~20 mm manual height adjustment** for 0–15 mm media.

| Mechanism | How pressure is set | Drive from the ZRIB | Notes |
|-----------|---------------------|---------------------|-------|
| **Gravity + servo** (first) | Weight of the pen slide (add weights to tune) | SERVO0 (pin 65), `M280 P0 S<angle>` | Simplest; pressure constant across the float range |
| Spring + servo | Long, soft spring pushes down; servo lifts against it | SERVO0 | Tunable; spring rate must be low |
| Solenoid / electromagnet | Gravity or spring presses; solenoid lifts | Spare MOSFET output (Fan1 D6 or Heater1 D7) via `M42`; flyback diode | Fast, quiet, binary; pen-down = de-energized (coil stays cool) |
| Permanent-magnet assisted | Magnets soften the landing or latch "up" | As above | Experimental |
| Stepper Z (lead screw) | Spring in the holder; Z position sets compression | Z driver + Z− endstop | Slow lifts; fallback |

### 3.4 Tool head and modularity (D8)

A **custom 3D-printed X carriage** with a defined **tool-plate interface** on its front face.
Every tool head (v1 pen holder, pen-lift experiments, future pen changer) is a separate
printed part. Start simple and evolve; the tool head is expected to be replaced.

**X carriage:**
- Rides on the upright 4020 beam: 2 V-wheels in the top groove, 2 in the bottom groove
  (**eccentric spacers on the bottom pair** for preload, D21; only 2 needed).
- Integrates the X belt clamp, the X endstop trigger, and strain relief for the tool-head cable.

**Tool-plate interface v1:**
- **Hook + 2 × M3:** a French-cleat hook along the top of the interface carries and
  locates the tool head: the carriage has a groove with a 45° undercut (6 mm opening, 3 mm
  deep), closed at both ends so it also locates the tool in X; the tool plate's lip drops
  into it. Two M3 screws into pressed-in nuts on the lower edge clamp it (36 mm apart,
  7 mm above the bottom edge). Fast to swap and repeatable.
- **Tool plate envelope:** ≤ 50 mm wide (it sits between the bottom wheels' bolt heads);
  interface 45 mm tall, bottom edge level with the carriage bottom.
- **Electrical:** one connector on the carriage for the tool head, in a 16 × 8 mm window in
  the carriage's top tab: 3-pin servo in v1, with space for a 4–6 pin connector later
  (solenoid, sensor, pen-changer signals). Zip-tie slots below it for strain relief.
- **Keep the pen close:** pen axis within ~25 mm of the carriage face, tip close below
  the beam.
- Exact dimensions live in `params.py`.

### 3.5 Controller and firmware (D9, D19)

**Board: Zonestar ZRIB v5.8** (ATmega2560, 6 socketed StepStick drivers, min and max
endstops on every axis, servo header, EXP1/EXP2, microSD, buck 5 V regulator).
Full analysis, pin map and bench checklist: [`docs/controller.md`](docs/controller.md).

**Firmware: Marlin 2.1.x** with `MOTHERBOARD BOARD_ZRIB_V53`. There is no v5.8
definition; V5.3 matches the 6 drivers (incl. E2) and the XS1 header. The pin map gets
verified on the bench with `M43` before we rely on it.

Why Marlin: it supports this board directly, plus servos (`M280`), dual Y steppers with
dual endstops, SD printing and the TFT35. The alternatives don't fit: GRBL/grbl-Mega would
need a custom pin map for this board, grblHAL targets 32-bit boards, and Klipper needs a
host computer.

**Allocation:**

| Function | Driver / input |
|----------|----------------|
| X motor | X driver |
| Y motor (left) | Y driver |
| Y2 motor (right) | E0 driver |
| X / Y / Y2 home | X− / Y− / Y+ input (as Y2 endstop) |
| Pen servo | SERVO0 (pin 65) |
| Pen-lift experiments | Z driver + Z− (stepper Z); Fan1/Heater1 MOSFET (solenoid) |
| Future pen changer | E1, E2 drivers; X+, Z+ inputs; XS1 pins |

**Heaters disabled:** `EXTRUDERS 0`, all `TEMP_SENSOR_*` set to 0, heater outputs left
unconnected (D19).

**Fallback:** the Creality board, if found and needed.

**BTT TFT35-E3 (optional):** in touch mode it talks to Marlin over serial and runs G-code
from its own SD/USB, so the plotter runs without a PC. Candidate port: Serial2 on EXP1
pins 3/4, or the AUX connector if that turns out to be serial (see `docs/controller.md`).
Not needed for v1.

### 3.6 Power

- Re-use the printer PSU: a **24 V, 15 A** unit (Cheng Liang P360W24V, 215 × 113 × 50 mm; the board
  accepts 12–24 V). With no heaters, three to four steppers draw far below its rating.
  The PSU stands **off the baseboard** on its own base (D30): its fan inlet is on the bottom
  face and needs free air, and the mains terminals stay off the machine's plywood.
- The servo runs from the ZRIB's buck 5 V regulator. Check during bring-up that the board
  doesn't reset when the servo stalls. If it does, add a separate 5 V buck converter
  (common GND).
- Mains: enclosed terminals, earthed PSU and frame, strain relief, switched inlet.

### 3.7 Homing, limits and coordinates

- **Origin at front-left** (X−, Y−). Homing order: Y (both sides square the gantry), then X.
- Endstops: X−; Y− (left) and the Y+ input used as the right-side Y2 endstop. Z− only if
  a stepper Z is used.
- Max limits by firmware soft limits (`X_MAX_POS`, `Y_MAX_POS` from the measured travel).
- After homing, the plot origin is set relative to the registration corner (§3.8),
  e.g. with `G92` or a workspace offset.

### 3.8 Frame, bed and work holding (D16)

**Principle: one flat reference.** The SK10 supports and the bed mount on the **same
baseboard**. The bed only needs to be parallel to the plane the pen moves in, not level
with gravity.

**Baseboard:**
- **18 mm plywood** (birch/multiplex), about **900 × 700 mm**: the mechanics plus room for
  electronics.
- **Extrusion runners** (2040/2020 offcuts) screwed across the underside, perpendicular
  to the shafts. They stop the board bowing, act as feet, and leave space underneath for
  the ZRIB and wiring.
- Electronics: the ZRIB (in its metal bracket) under the board between the runners; the
  PSU beside the machine (§3.6). Driver cooling fan.
- Cables moving with the gantry (X motor, X endstop, tool head): printed drag chain or a
  loose loom.

**Bed:** a separate **bed panel** (6–9 mm plywood/MDF) with a **0.5–1 mm galvanized steel
sheet** bonded on top. Flat magnets hold the media anywhere, and nothing at the sheet
edges can catch on the head. The panel sits on **4 adjustment points** (M5 screws with
nuts, or springs and thumb-nuts) above the baseboard. Alternative: 3–5 mm cast acrylic
with clips. Glass isn't needed. The final bed choice is made at build time.

**Leveling (once, then occasionally):** a dial gauge, feeler gauge or sheet of paper under
the pen holder. Jog to the four corners and the center, and adjust until the gap is
within ±0.3 mm.

**Z error budget the pen head must absorb (D18):**

| Source | Estimate |
|--------|----------|
| Shaft sag (mid-span vs ends) | 0.2–0.4 mm |
| Bed flatness after adjustment | ±0.3 mm |
| Residual board/panel bow | ~0.3 mm |
| Media unevenness (warped card, wood) | 0.5–1.5 mm |
| **Total** | **~±1.5 mm** → ≥ 3 mm float, ≥ 5 mm lift (§3.3) |

**XY squareness and registration:**
- Dual Y endstops square the gantry at every homing. X-to-Y squareness is set once when
  mounting the beam on its end brackets, and checked by plotting a large square and
  comparing diagonals.
- **Registration corner:** the machine draws an L-shaped reference line at the sheet
  origin. Fix printed or magnetic stops along it so sheets go in square to the machine axes.

### 3.9 Software

**First:** hand-written or small scripted G-code test patterns (squares, circles, grids,
pen up/down tests), sent over USB (Pronterface / any Marlin host) or from the SD card.

**Later:** an SVG/PDF → G-code workflow. Likely candidates: Inkscape or generative
code → `vpype` (merge, sort, simplify paths) → G-code with pen up/down mapped to `M280`
(or to the chosen pen-lift commands) → sender. Deferred until the machine runs (D20).

---

## 4. Design decisions

High-level decisions that shape the project. Each has an ID that is referenced from code
and docs. To change one, see §7.1. Lower-level and in-progress decisions (D11, D17, D20–D24
and newer) are in the decision log in [`STATUS.md`](STATUS.md).

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Metric units throughout | Project rule |
| D2 | CAD in PythonSCAD (Python), parametric | Project rule; one scriptable, testable source |
| D3 | Off-the-shelf / 3D-printer parts + printed parts only | Project rule |
| D4 | Pen lift is a v1 requirement | §3.3 |
| D5 | Cartesian moving-gantry layout (not CoreXY) | §3.1 |
| D6 | Y = 2 × Ø10 × 700 mm shafts on SK10 supports, 2 SCS10UU blocks per side | §3.2; replaces an earlier SBR12 plan (none on hand) |
| D7 | GT2 belt drive on X and Y; lead screws only for an optional pen-Z experiment | §3.2 |
| D8 | Printed X carriage with a hook + 2 × M3 tool-plate interface and a tool-head connector; tool heads are separate printed parts; no extrusion spine in v1 | §3.4 |
| D9 | Controller: ZRIB v5.8 with Marlin `BOARD_ZRIB_V53`; Y2 on E0; servo on SERVO0 | §3.5; pin map verified on the bench |
| D10 | Target media A3 and smaller; A3 short side across X | R3, §3.2 |
| D12 | X beam: 520 mm 4020 V-slot mounted upright (~426 mm X travel) | §3.2 |
| D13 | Dual Y motors with one endstop per side (auto-squaring) | §3.2 |
| D14 | Pen-lift mechanism chosen by experiment; start with gravity + servo | §3.3 |
| D15 | Media thickness 0–15 mm | R2 |
| D16 | 18 mm plywood baseboard (~900 × 700 mm) with extrusion runners underneath; shafts and bed share it as the reference | §3.8 |
| D18 | Pen head absorbs ±1.5 mm Z error: ≥ 3 mm float with near-constant pressure, ≥ 5 mm lift | §3.8 |
| D19 | Heaters disabled in firmware (`EXTRUDERS 0`, sensors 0) and left unconnected | §3.5 |

---

## 5. Repository layout

```
Plotter/
├── README.md            ← overview, design, standards, contribution guidelines (this file)
├── STATUS.md            ← ongoing development: work plan, decisions, open questions
├── CLAUDE.md            ← instructions specific to AI agents
├── pyproject.toml       ← Python project: plotter_cad package, deps, pytest/ruff/mypy/uv config
├── Makefile             ← shortcuts: make develop / check / typecheck / format / lint / test / stl / render / clean
├── uv.lock              ← locked dependency versions (uv)
├── .python-version      ← Python version for pyenv and uv (3.14)
├── docs/
│   ├── controller.md    ← ZRIB v5.8 analysis, pin map, bring-up checklist
│   ├── hardware.md      ← vendor part dimensions for CAD
│   └── sketch-formats.md ← research on parametric 2D sketch formats
├── src/plotter_cad/     ← CAD (PythonSCAD); paths in the docs are relative to it
│   ├── params.py        ← shared parameters, derived values, design checks
│   ├── geometry.py      ← $fn settings, teardrop holes, SVG sketch loader and other helpers
│   ├── hardware/        ← vendor-part dimensions and models (SK10, SCS10UU, NEMA17…),
│   │                      plus SVG sketches of profiles (vslot_2020.svg, vslot_2040.svg)
│   ├── parts/           ← printable parts, one module each (print orientation)
│   ├── assemblies/      ← fit-check assemblies (gantry, carriage, skeleton, gallery)
│   └── build.py         ← CLI: python -m plotter_cad {check,stl,render,all}
├── stubs/pythonscad/    ← type stub for the untyped pythonscad module
├── tests/               ← pytest: design rules, sane printable solids, connected assemblies
├── stl/                 ← exported printable parts (generated by `make stl`; git-ignored)
├── renders/             ← PNG renders of parts and assemblies (generated by `make render`; git-ignored)
├── firmware/            ← Marlin configuration and build notes
└── software/            ← test patterns, toolchain scripts
```

---

## 6. Development setup and workflow

The CAD is plain Python on top of the [PythonSCAD](https://pythonscad.org) `pythonscad`
module (OpenSCAD's geometry engine with a Python API). Conventions: §7.4.

**Setup (once):** Python ≥ 3.14 from [pyenv](https://github.com/pyenv/pyenv), packages
managed with [uv](https://docs.astral.sh/uv/). `.python-version` pins 3.14 for both
tools; `[tool.uv] python-preference = "only-system"` in `pyproject.toml` makes uv use the
pyenv interpreter instead of downloading its own. Dependencies are locked in `uv.lock`.

```bash
cd Plotter
pyenv install --skip-existing 3.14            # any 3.14.x
uv venv --python "$(pyenv which python)"      # creates .venv on the pyenv interpreter
uv sync --extra dev                           # plotter_cad + pythonscad + pytest + ruff + mypy
source .venv/bin/activate                     # or prefix commands with `uv run`
```

`make develop` runs these steps. After changing dependencies in `pyproject.toml`, run it
(or `uv sync --extra dev`) again; it updates `uv.lock`.

**Shortcuts (`Makefile`):** `make develop` (set up the environment), `make check` (mypy,
ruff lint + format check; changes nothing), `make typecheck` (mypy only), `make format`
(re-format the code), `make lint` (ruff lint with automatic fixes), `make test` (pytest),
`make stl` (all STLs), `make render` (all PNG renders; needs the PythonSCAD app),
`make clean` (delete `stl/`, `renders/`, caches and build output; keeps `.venv`).
`make` lists them.

For renders and interactive preview, also install the PythonSCAD app
(pythonscad.org/downloads; on macOS it is found at `/Applications/PythonSCAD.app`).

**Commands:**

| Command | What it does |
|---------|--------------|
| `python -m plotter_cad check` | Design checks + key numbers |
| `python -m plotter_cad stl [names]` | Export printable parts to `stl/` |
| `python -m plotter_cad render [names]` | PNGs of parts and assemblies to `renders/` (needs the app; `--pythonscad PATH` or `$PYTHONSCAD`) |
| `python -m plotter_cad all` | All of the above |
| `python -m pytest` | Tests: design rules hold, every part is a sane printable solid, assembly parts connect (philosophy: §7.6) |
| `mypy` | Type checks (§7.5) |
| `ruff format . && ruff check .` | Formatting and lint (PEP 8) |

After an intentional geometry change: review the new STLs/renders.

**2D sketches (trial, D23):** a shape that is easier to draw than to code can be an
SVG file next to the Python module that uses it. `geometry.load_sketch(path)` imports it
as a 2D object, which the module extrudes:

```python
profile = load_sketch(Path(__file__).with_name("vslot_2040.svg"))
beam = linear_extrude(profile, height=520)
```

- Draw at **1 user unit = 1 mm**: `width`/`height` in mm and a `viewBox` with the same
  numbers. The viewBox's bottom-left corner is the CAD origin; the sketch keeps the
  orientation it is drawn in.
- Every shape is imported **filled**; strokes and colors are ignored and separate
  shapes are unioned. Make holes sub-paths of one `<path>` with `fill-rule="evenodd"`
  (Inkscape: *Path → Combine*). Convert text and clones to paths.
- A profile used at several lengths is loaded directly (`vslot_x(length, size)` picks
  the 2020 or 2040 sketch). A part with fixed 3D dimensions gets a module with the same
  name as its sketch (`foo.svg` + `foo.py`) that extrudes it.
- The sketches can be edited in Inkscape or as text; note the dimensions in a comment at
  the top of the file.
- Parametric/constrained sketches: draw them in your CAD tool (e.g. FreeCAD) and export
  the solved outline as SVG into the repo (D24); the SVG is the source for PythonSCAD.

**Interactive preview:** open `preview.py` (repo root) in the PythonSCAD app, set the
part or assembly name at the top, and render (F6). It adds `src/` to the path itself.

---

## 7. Contribution guidelines and coding standards

These apply to everyone working on the project, human or AI agent.

### 7.1 Working on the project

- Pick work from the task list in [`STATUS.md`](STATUS.md); do **one task at a time** and
  check its "done when" criterion.
- Before designing around an unknown dimension or fact, **measure or check it** (photos
  welcome) instead of guessing. Mark any assumed value clearly as `ASSUMED` in code and as
  *assumed* in docs.
- Check the inventory (`STATUS.md`) and `docs/hardware.md` before designing around a part.
- **Don't silently change a decision.** High-level decisions are in §4, detailed ones in
  `STATUS.md`. To change one, propose it, explain the trade-off, and update the log once
  it is agreed.
- When comparing options, give a short table of trade-offs and a recommendation.
- When a task is finished: tick it in `STATUS.md`, add follow-up tasks, record new or
  changed decisions and open questions there, update its inventory, key numbers and
  as-built notes (and `docs/`) with any new facts or measurements, and update its status
  line.

**Hard rules**

1. **Metric only.** Millimeters, degrees, mm/s (or mm/min where G-code requires it, and
   say which). No imperial units or fasteners.
2. **Hardware is off-the-shelf or salvaged 3D-printer parts.** Metric hex fasteners
   (M2.5/M3/M4/M5, ISO 4762 socket head preferred), pressed-in (captive) hex nuts (**no heat-set inserts**, D29),
   NEMA17 steppers, GT2 belts/pulleys, T8 lead screws, 608/625 bearings, LM6UU/LM8UU,
   Ø10 mm shafts with SK10 supports and SCS10UU blocks, 2020/2040/4020/4040 V-slot extrusion.
   Anything else must be justified and noted in this README.
3. **CAD is PythonSCAD (Python).** The `plotter_cad` package under `src/` is the only CAD
   source (D2). No other CAD formats as sources, with one exception on trial (D23):
   2D sketches as SVG files next to the module that extrudes them (§6). STLs and renders
   are generated outputs.
4. **Safety:** printer heaters stay disabled in firmware and unconnected; mains wiring
   enclosed and earthed.

### 7.2 Design constraints

- **Keep the gantry light.** The Y shafts are end-supported Ø10 mm shafts that sag
  ~0.2–0.4 mm under the gantry (§3.2).
- **Pen head:** ≥ 5 mm lift, ≥ 3 mm float with near-constant pressure, ~20 mm manual
  height adjustment, 7–16 mm pens, pen close to the carriage face (§3.3, §3.4).
- **Modularity:** tool heads attach only through the tool-plate interface (hook + 2 × M3,
  §3.4). Don't couple tool-head geometry to the carriage beyond that interface.
- **Clearance:** 15 mm media must pass under the head and gantry everywhere in the travel.
- **Simplicity over performance:** prefer the easy-to-build, easy-to-debug option.
- **Serviceability:** belts tensionable without disassembly; motors, boards and tool
  heads replaceable with hand tools.

### 7.3 Documentation

- Keep this README concise; prefer tables for comparisons and decisions. It holds what
  rarely changes; anything tied to the progress of the work goes in `STATUS.md`.
- **US English spelling** everywhere: docs, comments, docstrings, identifiers, sketch
  comments (center, color, modeled, leveling, aluminum, millimeter, catalog...).
- Longer research, procedures and results go in `docs/<topic>.md` (e.g.
  `docs/pen-lift.md`, `docs/calibration.md`), linked from this README or `STATUS.md`.
- Don't store vendor datasheets or drawings in the repository (copyright). Record the
  values for the specific parts we use in `docs/hardware.md` and note where they came from.
- Electronics wiring and pin allocation live in `docs/controller.md`; keep it current
  (mark items verified after bench tests).

### 7.4 CAD conventions (PythonSCAD)

The CAD is a Python package, `plotter_cad` (`src/plotter_cad/`), built on the
[PythonSCAD](https://pythonscad.org) `pythonscad` module (OpenSCAD's geometry engine
with a native Python API). Setup and commands are in §6.

- **Environment:** Python ≥ 3.14 from pyenv (`.python-version`), virtualenv in `.venv`,
  dependencies managed by uv (`uv sync --extra dev`, locked in `uv.lock`). Run commands
  in the activated `.venv` or with `uv run` (e.g. `uv run python -m pytest`). Don't
  install packages with `pip`; add them to `pyproject.toml` and re-sync.
- **Parametric first.** Shared dimensions in `params.py` (travel, shaft spacing,
  clearances, tolerances, tool-plate interface), grouped into frozen dataclasses with one
  module-level instance each (`TOL`, `BEAM`, `CARRIAGE`, `TOOL_PLATE`...). Vendor-part
  dimensions and simple models in `hardware/` (`SK10`, `SCS10UU`, `NEMA17`, `VWHEEL`,
  fasteners...). Derived values are `@property`s, never typed-in numbers. No magic
  numbers in part modules: add a parameter instead.
- **2D sketches (trial, D23):** an SVG next to the module that uses it, loaded with
  `geometry.load_sketch()`; 1 unit = 1 mm, origin at the viewBox's bottom-left, holes as
  `evenodd` sub-paths, dimensions noted in a comment in the file (§6). So far
  only for vendor-part profiles (`hardware/vslot_*.svg`); printed parts stay parametric
  in Python unless a sketch is requested.
- **Design rules** live in `params.design_checks()`; `check_design()` raises
  `DesignError`. Add a rule whenever a new constraint appears (clearance, travel, fit).
- One printable part per module in `parts/`, exposing a function that returns the part
  in its **print orientation** (flat face on z = 0), plus `*_installed()` / `*_left()`
  helpers when the part is designed in another frame. Register every printable part in
  `parts.PRINTABLE_PARTS` (name = STL file name).
- Assemblies in `assemblies/` return lists of colored solids (parts + hardware models)
  for fit checks; register them in `assemblies.ASSEMBLIES`.
- Default print tolerances (tune after a test print; keep them in `params.TOL`):
  - Bolt clearance holes: nominal + 0.3–0.4 mm (M3 → 3.4 mm, M5 → 5.4 mm)
  - Sliding fit +0.2 mm; press fit −0.1 to 0 mm
  - Nut traps: across-flats + 0.3 mm
  - Minimum wall: 1.6 mm (4 perimeters at 0.4 mm nozzle)
- **Handles:** a part that hardware or other parts attach to exposes named handles
  (`geometry.set_handles` / `get_handle`) and assemblies place things with `.align(handle)`
  rather than repeating the part's coordinates (D28).
- Prefer designs printable without supports (teardrop holes from `geometry.py`, 45°
  overhangs); note any required supports in the module docstring.
- Each part module starts with a docstring: purpose, required hardware (with
  quantities), print settings (material, layer height, infill, orientation).
- Facet counts: pass `fn=` explicitly; use `geometry.FN` / `geometry.FN_HOLE` (64) for
  printed geometry, lower counts only for hardware models.
- **Before handing over a CAD change:** `make check` and `make test` pass;
  `python -m plotter_cad stl` regenerates `stl/`; `python -m plotter_cad render`
  regenerates `renders/` (needs the PythonSCAD app). If geometry changed on purpose,
  review the STLs/renders.

### 7.5 Python coding standards

- PEP 8, enforced by `ruff format` and `ruff check` (config in `pyproject.toml`,
  line length 100).
- Import PythonSCAD names explicitly (`from pythonscad import cube, cylinder`), never
  `from pythonscad import *`.
- Prefer the method style for transforms (`cube(...).rotate(...).translate(...)`): it
  reads in the order the operations happen. Note that this is the reverse of the
  OpenSCAD nesting order.
- Don't give a function the same name as its module inside a package `__init__`
  (`from .x_carriage import x_carriage` shadows the submodule); import modules there.
- Mark assumed values with an `ASSUMED` comment, design choices with `DESIGN (Tn.m)`.

#### Type annotations

- All code must pass type checking with `mypy` (`make typecheck`, part of `make check`;
  strict mode, config in `pyproject.toml`). Annotate all new functions and public
  attributes.
- Follow PEP 604 (`X | Y` unions) and PEP 673 (`Self`).
- Use `collections.abc` for generic collection types over deprecated `typing` types.
- Prefer structural typing (duck typing) such as `Protocol`s over strict inheritance,
  unless inheritance also serves other purposes beyond type adherence (such as code reuse).
- `pythonscad` ships no type information: the local stub `stubs/pythonscad/__init__.pyi`
  provides it, including the `Solid` type. `Solid` exists only in the stub, so import it
  under `if TYPE_CHECKING:` (annotations are lazy in Python 3.14). Extend the stub when
  using a new PythonSCAD function or method.

#### Comments and docblocks

- Files, classes and functions have a short docblock (at least a one-liner, PEP 257 style)
  describing the purpose of the unit: "what this is", not "how this works".
- A Google-style docstring may describe a function in more detail, beyond what naming and
  type annotations already say, if necessary.
- Inline comments should be rare, and never explain what the code does or repeat what is
  obvious from reading it.
- A short inline comment is fine for a non-obvious block or something others may find
  confusing or counter-intuitive, but code should be self-documenting; a comment is a
  last resort.

### 7.6 Testing

Tests exist to make changes faster and safer: they should fail when the code is broken
and stay quiet when a design value changes on purpose. A test that only makes changes
slower has negative value; delete it.

**Test:**
- Pure functions that are reused or more than trivial (geometry helpers, the sketch
  loader, the measuring helpers in `tests/solids.py`).
- Solids are sane: every printable part is one piece with no enclosed voids, has a
  plausible volume and rests on the print bed.
- Assemblies hold together: parts touch what they mount on, nothing floats.
- Behavior at the public interface: the design rules pass, a broken rule is reported,
  errors for bad input, the STL export writes its files.

**Don't test:**
- Parameter or geometry values that are expected to change (key numbers, reference
  volumes or bounding boxes). That duplicates the configuration and breaks on every
  intended change. A real constraint belongs in `params.design_checks()` instead.
- Trivial behavior: Python operators, one-line arithmetic, other libraries.
- Implementation details and private (`_name`) code.
- Anything through a mock that replaces the code under test. Overriding a parameter
  set (e.g. `dataclasses.replace` on a params instance) is fine; faking the
  implementation is not.

Run with `make test`. Assemblies are fit-check models: when a connection test fails
because a model is too crude (a missing nut or bushing), fix the model.

### 7.7 Firmware

- Marlin 2.1.x, `BOARD_ZRIB_V53`. Keep the configuration under `firmware/` (full files or
  a diff against a stated Marlin version) with build and flash notes.
- Never enable heaters or thermal outputs.
