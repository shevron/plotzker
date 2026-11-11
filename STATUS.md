# Project status

The state of the ongoing development: where we are, what is next, open questions,
detailed decisions, inventory, key numbers, as-built design notes and ideas. Goals,
requirements, the high-level design and the coding standards are in
[`README.md`](README.md); references like "README §3.2" point there.

> **Status:** Phase 1 (architecture) complete. Phase 3 in progress: T3.1–T3.5 done (CAD
> scaffold, gantry end brackets, X carriage, X motor/idler/endstop mounts, Y motor/idler/
> endstop mounts (endstop mounts redone for the measured board); STLs in `stl/`, test prints pending). CAD migrated from OpenSCAD to PythonSCAD (T3.9, D22; identical
> STLs). On trial: SVG 2D sketches for profiles (D23; V-slot 2020/2040). Open: Q12 (beam
> ends tapped?). Q10 (SVG/PDF toolchain) deferred until the machine runs.
>
> **Next:** T3.6 v1 pen holder (tool head; check the servo model first). Phase 2 can run in
> parallel.

**Contents:** 1 Work plan · 2 Open questions · 3 Decision log · 4 Inventory ·
5 Key numbers · 6 As-built design notes · 7 Ideas and future possibilities

---

## 1. Work plan

### Build phases

| Phase | Name | Output | Status |
|-------|------|--------|--------|
| 0 | Inventory & requirements | README §2, §4 | ✅ Done |
| 1 | Architecture decisions | README §3, §4 | ✅ Done |
| 2 | **Electronics bench bring-up** | Marlin configured and flashed; pin map verified; motors, endstops and servo working on the bench | Next |
| 3 | **Mechanical CAD (PythonSCAD)** | Parametric model: gantry, carriage, mounts, v1 pen holder, baseboard layout | 🔧 In progress |
| 4 | Print & assemble | Baseboard, Y axis, gantry, X axis, wiring | — |
| 5 | Integration & calibration | Homing, squaring, steps/mm, soft limits, bed leveling | — |
| 6 | First plots & pen-lift experiments | Test patterns from hand-written/scripted G-code; pen-lift mechanism chosen (Q6) | — |
| 7 | Software toolchain | SVG/PDF → G-code workflow (Q10) | Deferred |
| 8 | Enhancements | Automatic pen change, other tools, TFT35 standalone use | — |

Phases 2 and 3 are independent and can run in parallel.

### Tasks

Tasks are sized for one working session each. When a task is done: tick it here, record
any new decisions in §3, and update the status line at the top.

#### Phase 2 — Electronics bench bring-up (see `docs/controller.md`)

- [ ] **T2.1 Read the hardware facts.** PSU label (voltage, current); chip markings on all
  6 drivers (A4988/DRV8825/other); microstepping jumpers under each socket; servo model.
  *Done when:* recorded in §4 and `docs/controller.md`.
- [ ] **T2.2 Configure Marlin.** Marlin 2.1.x; store config in `firmware/` (full
  `Configuration.h` / `Configuration_adv.h` or a diff, plus build notes). Key settings:
  `BOARD_ZRIB_V53`, `EXTRUDERS 0`, `TEMP_SENSOR_* 0`, `Y_DUAL_STEPPER_DRIVERS`,
  `Y_DUAL_ENDSTOPS` (+ `Y2_USE_ENDSTOP _YMAX_`), `NUM_SERVOS 1`, driver types, 80 steps/mm
  for X/Y, travel limits (~410 × 540), `PINS_DEBUGGING` (for `M43`), SD card support.
  *Done when:* it compiles (PlatformIO, `mega2560` env).
- [ ] **T2.3 Flash and verify the pin map.** Flash over USB. Check every endstop with
  `M43 W` / `M119`. Jog each driver socket with one motor attached; confirm E0 drives Y2.
  *Done when:* the pin map in `docs/controller.md` is marked verified, or corrected.
- [ ] **T2.4 Servo and 5 V test.** Find the servo header (likely XS2). Check `M280 P0 S<angle>`
  sweeps, and that the board doesn't reset with the servo stalled.
  *Done when:* header and angle range recorded; decision on a separate 5 V supply.
- [ ] **T2.5 Driver current (Vref).** Set Vref for the motors in use; both Y drivers identical.
- [ ] **T2.6 (Optional) TFT35-E3.** Identify the AUX connector pins; connect the TFT in touch
  mode (Serial2 on EXP1 or AUX).

#### Phase 3 — Mechanical CAD (PythonSCAD; conventions in README §7.4, workflow in README §6)

- [x] **T3.1 Scaffold the CAD.** `params.py` (travel, shaft spacing, clearances,
  print tolerances, tool-plate interface dimensions), `hardware/` (models of NEMA17,
  GT2 pulley, SK10, SCS10UU, 2020/4020, V-wheel, fasteners, from `docs/hardware.md`).
  Measure first: SK10 hole spacing/size, NEMA17 body length, belt width, V-wheel dimensions.
  - [x] Files written with catalog values marked `ASSUMED`; derived stack-up, travel
    and clearance checks (now `params.design_checks()`); `assemblies/skeleton.py` (layout check) and
    `hardware_gallery.py`. All render without errors.
  - [x] SK10: vendor table (values in `docs/hardware.md`): 2 × M5 on 32 mm, W 42,
    F 37.5, L 14, base 6.
  - [x] 4020 confirmed V-slot (user).
  - [x] NEMA17: design for 39.2 mm body / 22.6 mm shaft; belt lines must fit the shortest
    shaft on hand (19 mm, 33.5 mm motor); 48 mm clearance envelope.
  - [x] 6 mm GT2 belt; common 20T pulleys and idlers; V-wheels Ø24 × 10. Design for common
    sizes, adjust at assembly. Eccentric spacers: only a few, don't rely on them (Q11).
  - Remaining measurements moved to the tasks that need them (T3.2, T3.3/T3.5, T3.6).
- [x] **T3.2 Gantry end brackets (×2).** Bolt to two SCS10UU (4 × M5 each, 28 × 21 mm), hold
  the 4020 beam square, include the Y belt clamp and the Y endstop trigger. Lift the beam
  bottom to ~58 mm (§6). Bracket bears on the SCS10UU's two 10 mm top flats (measured).
  → `parts/gantry_end_bracket.py` (left/right), `parts/y_belt_clamp.py` (×4),
  `assemblies/gantry.py`; STLs in `stl/`. The endstop switch itself mounts in T3.5.
  - [ ] Follow-up: answer Q12 (beam ends tapped?); test-print one bracket and check the fit
    on the SCS blocks, the beam pocket and the belt clamp before printing the pair.
- [x] **T3.3 X carriage.** 4 V-wheels on the 4020 (eccentric bottom pair, D21), X belt clamp,
  X endstop trigger, tool-plate interface (hook + 2 × M3), connector mount, cable strain relief.
  Eccentric spacers measured (10 mm hex × 7.8, Ø7 × 2.1 boss, ~0.7 mm offset): bottom wheels
  sit 8.3 mm from the plate face; the top wheels match on printed stand-offs.
  → `parts/x_carriage.py` (+ `Preload.SLOT` fallback),
  `assemblies/carriage.py`; STL in `stl/`. Checked: no collision with the gantry
  brackets at either end of travel, incl. a 50 × 60 mm tool-head envelope.
  - [ ] Follow-up: test-print; check wheel preload range, hook-groove fit (with the T3.6 tool
    plate) and the X belt clamp. (STL regenerated in T3.4: belt line 4 mm further back.)
- [x] **T3.4 X motor mount and X idler** at the beam ends. → `x_motor_mount.py` (right end,
  printed mirrored), `x_idler_mount.py` + `x_idler_spacer.py` (left end, slot tensioner),
  `x_endstop_mount.py` (X− switch on the idler mount); assembled in
  `assemblies/gantry.py`. The X belt line moved 4 mm back (center 23 mm behind the beam
  center) so the motor plate fits between the bracket's rear bolt rows and 22.6 mm motor
  shafts clear the beam; the carriage regenerates from `params.py` (new STL; trigger now
  at z ~114.5). Checked: no collisions with the carriage at either end of travel.
  - [ ] Follow-up: check the endstop board's hole positions and connector side against
    `x_endstop_mount.py` (assumed: holes across the width, 4 mm from the far end; connector
    on the switch side); test-print and check belt tension range and switch trip point.
- [x] **T3.5 Y motor mounts, Y idlers and belt tensioners** (on the baseboard, in line with
  each shaft), and the Y endstop mounts. Belt 30 mm outboard of each shaft; motor shaft /
  idler axle at `Y_AXIS.pulley_axis_z` (~27.8 mm). The X− endstop was done in T3.4.
  → `parts/y_motor_mount.py`, `y_idler_mount.py`, `y_endstop_mount.py` (each left + mirrored
  right, so 6 STLs), `assemblies/y_drive.py` (also drawn in the skeleton). Endstop board
  confirmed by the user: M3, holes across the width at the connector end.
  Checked: no collisions with the gantry, SK10s or shafts at the front, middle or back of
  Y travel (test); only the endstop lever is touched by the trigger screw at the front end.
  - [ ] Follow-up: re-measure the endstop hole pitch (15 mm measured; the photo suggests
    ~17–18 mm); test-print; check belt tension range, the trip point (adjust with the
    trigger screw length) and the idler plate against the wood-screw positions on the
    baseboard.
- [ ] **T3.6 v1 pen holder (tool head).** Vertical slide, V-groove clamp for 7–16 mm pens,
  ~20 mm height adjustment, servo mount, gravity loading with room for added weight; meets
  the README §3.3 requirements. Interface: `TOOL_PLATE` in `params.py` (≤ 50 mm wide, hook
  lip for the 45° groove, 2 × M3); cable to the connector window in the carriage top tab.
  *Check first:* servo model.
- [ ] **T3.7 Full assembly and baseboard layout.** Assembly model for fit checks (travel,
  clearances, 15 mm media under the head). 1:1 baseboard drilling layout: SK10 positions,
  motor mounts, bed-panel adjustment points, runners, electronics.
- [ ] **T3.8 Cable management.** Drag chain or cable guide from the gantry to the board.
- [x] **T3.9 Migrate the CAD to PythonSCAD (D22).** Sanity test: PythonSCAD renders the
  old `.scad` files to the same STLs. Port to a Python package (`src/plotter_cad/`:
  `params.py`, `hardware/`, `parts/`, `assemblies/`, `build.py` CLI) with pytest tests
  and ruff. Checked: all 8 STLs geometrically identical to the OpenSCAD ones (volume,
  bounding box, cross-sections; incl. the `Preload.SLOT` fallback); assemblies match by
  volume and bounding box; same key numbers. The old `.scad` files were removed afterwards.

#### Phase 4 — Build

- [ ] **T4.1** Cut the baseboard and bed panel; fit the runners; drill from the T3.7 layout.
- [ ] **T4.2** Mount the SK10s and shafts; fit the gantry; align the shafts (README §3.2
  procedure).
- [ ] **T4.3** Fit the beam, carriage, motors, belts and endstops; check that the axes move
  freely by hand.
- [ ] **T4.4** Mount the electronics and PSU; wire everything; safety checks on mains wiring.

#### Phase 5 — Integration & calibration

- [ ] **T5.1** First homing (Y squaring, then X); set soft limits from the measured travel.
- [ ] **T5.2** Steps/mm check (draw/measure a 300 mm line); squareness check (diagonals of a
  large square); belt tension.
- [ ] **T5.3** Bed leveling (README §3.8); set the pen-down height and the float.

#### Phase 6 — First plots & pen-lift experiments

- [ ] **T6.1** Test-pattern G-code in `software/test-patterns/` (squares, circles, grids,
  text, pen up/down stress test); speed/acceleration tuning.
- [ ] **T6.2** Pen-lift experiments (Q6): gravity + servo, then spring + servo and
  solenoid/magnet options; compare pressure consistency, line quality and speed; record the
  results in `docs/pen-lift.md` and choose a mechanism.
- [ ] **T6.3** Registration corner (README §3.8).

#### Phase 7 — Software toolchain (Q10)

- [ ] **T7.1** Choose and document the SVG/PDF → G-code workflow.

#### Phase 8 — Enhancements (backlog)

- Automatic pen changing; TFT35 standalone plotting; other tool heads (see §7).

---

## 2. Open questions

| ID | Question | Status |
|----|----------|--------|
| Q1 | Controller boards | ✅ ZRIB v5.8; Creality board TBD (fallback); TFT35-E3 is a screen/SD sender |
| Q2 | Parts inventory | ✅ Enough to proceed; remaining measurements listed in the tasks (T2.1, T3.1) |
| Q3 | Work area, rail length, media thickness | ✅ A3; ~540 mm Y travel; 0–15 mm media |
| Q4 | Cartesian vs CoreXY | ✅ Cartesian |
| Q5 | Gantry drive and squaring | ✅ Dual Y motors + dual endstops |
| Q6 | Pen lift and thickness handling | 🔬 Approach decided; mechanism chosen by experiment (T6.2) |
| Q7 | Firmware and board mapping | ✅ Marlin `BOARD_ZRIB_V53`; verified in T2.3 |
| Q8 | Tool-plate interface and v1 pen holder | ✅ README §3.4 |
| Q9 | Frame, baseboard and work holding | ✅ README §3.8 (bed material finalized at build) |
| Q10 | SVG/PDF → G-code toolchain | ⏸ Deferred to phase 7 |
| Q11 | X-carriage wheel preload | ✅ D21: 2 eccentric spacers on the bottom pair; slot + push-screw fallback |
| Q12 | Are the 4020 beam ends tapped M5 (gantry brackets bolt into the end bores)? | ❓ User to check; else tap M5 or let an M5 screw cut its own thread |

---

## 3. Decision log

Detailed and in-progress decisions. The high-level decisions (D1–D10, D12–D16, D18, D19)
are in README §4; IDs are shared and never reused. To change a decision, propose it and
update the log once it is agreed (README §7.1).

| ID | Decision | Status | Ref |
|----|----------|--------|-----|
| D11 | Y travel ~540 mm; Y length parametric in CAD | ✅ | README §3.2, Q3 |
| D17 | Bed: adjustable panel (4 points) with a bonded steel sheet and magnets; acrylic as alternative; no glass | 🟡 Proposed (final choice at build) | README §3.8 |
| D20 | SVG/PDF toolchain deferred; prove the machine with hand-written/scripted G-code first | ✅ | README §3.9, Q10 |
| D21 | X-carriage preload: 2 eccentric spacers on the bottom wheel pair. Fallback if 2 can't be found: slotted axle holes + M3 push screw, clamped by the axle nut (`CARRIAGE.preload` in `params.py`) | ✅ | README §3.4, Q11 |
| D22 | Migrate the CAD from OpenSCAD to PythonSCAD: a `plotter_cad` Python package (`src/`), pip `pythonscad` module for STL export, PythonSCAD app for renders/preview. Ported 1:1 (all 8 STLs geometrically identical); the old `.scad` files were removed afterwards. D2 originally named OpenSCAD | ✅ | README §6, T3.9 |
| D23 | **Experiment:** 2D sketches as SVG files next to the module that extrudes them (sketch → extrude workflow), loaded with `geometry.load_sketch()`. First use: the V-slot 2020/2040 profiles (`hardware/vslot_2020.svg`, `vslot_2040.svg`). PythonSCAD stays the only 3D source; printable parts stay fully parametric in Python for now | 🔬 Trial | README §6 |
| D24 | Parametric sketch formats researched (`docs/sketch-formats.md`): no open interchange format carries sketch constraints. A Python constraint-sketch module (python-solvespace) was tried on the 2020 profile and **rejected**: it doesn't allow GUI drawing and adds little over plain PythonSCAD. **Stay with SVG (D23)**: designers draw and constrain in their CAD tool (e.g. FreeCAD) and export SVG. Revisit: automate the export with FreeCAD as a dependency | ✅ | `docs/sketch-formats.md` |
| D25 | Y drive layout: motor **behind the rear SK10**, shaft outboard, belt 30 mm outboard of the shaft; idler with slot tensioner in front of the front SK10; Y endstops at the **front** on both sides, on a tower of the idler mount; printed mounts screwed to the baseboard with M4 wood screws (*assumed* size). Costs ~25 mm of baseboard length at the back; belt ~1.4 m per side | ✅ | T3.5, §6 |

---

## 4. Inventory (parts on hand)

Working assumption: any **commonly available** 3D-printer / maker part can be obtained.
Parts listed here are ones we specifically plan around. If something turns out to be
hard to get, we adjust.

| Part | Qty | Details | Still to confirm |
|------|-----|---------|------------------|
| 2020 V-slot extrusion | several | **520 mm** long | — |
| 4020 V-slot extrusion | 2 | **520 mm** long → X beam; V-slot profile confirmed | Ends tapped M5? (Q12) |
| Shorter 2020 / 2040 / 4040 extrusions | assorted | e.g. 340 mm 2040 → baseboard runners/feet | Lengths |
| V-wheels | many | POM V-groove wheels on 625Z bearings (5 mm bore), Ø24 × 10 mm; eccentric spacers: 10 mm hex × 7.8, Ø7 × 2.1 boss, Ø5 bore, ~0.7 mm offset (2 needed, D21) | — |
| Ø10 mm smooth (optical-axis) shafts | 2 | **700 mm**, hardened → Y axis | — |
| SK10 shaft supports | 4 | End supports, shaft center **20 mm** above the mounting surface; 2 × M5 on 32 mm, 42 W × 37.5 H × 14 L ([`docs/hardware.md`](docs/hardware.md)) | — |
| SCS10UU linear bearing blocks | 4 | 2 per shaft; 35 L × 40 W × 26.5 H mm, shaft center 13 mm above the base, 4 × M5 top holes on 28 × 21 mm, top: two 10 mm raised flats (holes in them) with a 17 mm × 1 mm recess between, 92 g ([`docs/hardware.md`](docs/hardware.md)) | — |
| NEMA17 stepper motors | ≥ 3 (+1 for optional Z) | Standard 3D-printer type; sizes vary: typical 39.2 mm body / 22.6 mm shaft, short 33.5 / 19 | — |
| GT2 belt, pulleys, idlers | assorted | 6 mm belt (plenty); common 3D-printer 20T pulleys and idlers | Exact pulley/idler sizes (design for common, adjust) |
| Lead screws, linear bearings, misc. bearings | assorted | | Only needed for a stepper Z experiment |
| Hobby servos | 2+ | Small, SG90-class assumed | Model |
| **Controller: Zonestar ZRIB v5.8** | 1 | ATmega2560, 6 socketed StepStick drivers ([`docs/controller.md`](docs/controller.md)) | Driver chip type; pin map (bench) |
| Controller: Creality (newer) | 1? | Not located yet; fallback | Model |
| BigTreeTech TFT35-E3 | 1 | Touch screen with its own MCU; **not a motion controller**. Optional UI and SD/USB G-code sender | Hardware version |
| Power supply | 1 | From a printer | **Voltage (12/24 V), current** |
| Endstop switches | ≥ 3 | Creality-type boards: 20 × 19 × 1.5 mm, M3 holes 15 mm apart at the rear, switch across the front edge, lever 5 mm out at rest / 1.5 mm pressed, ~12 mm thick incl. connector (`docs/hardware.md`) | Click point, lever length |
| Plywood, steel sheet, magnets | to buy/cut | Baseboard, bed panel, work holding (README §3.8) | — |

---

## 5. Key numbers (quick reference)

| Item | Value |
|------|-------|
| X travel / Y travel | ~426 mm / ~543 mm |
| Target media | A3 and smaller, 0–15 mm thick |
| Steps/mm (GT2, 20T, 1.8°, 1/16) | 80 |
| Shaft center height above the mounting surface | 20 mm |
| SCS10UU top face above the mounting surface | 33.5 mm |
| SCS10UU top mounting holes | 4 × M5, 28 (across) × 21 (along) mm |
| Bed top / thickest media top (above baseboard) | ~15 mm / ~30 mm (*design values*) |
| X beam bottom / top (above baseboard) | ~58 / ~98 mm (carriage clears 15 mm media by 3 mm) |
| Expected shaft sag | 0.2–0.4 mm |
| Pen head | ≥ 5 mm lift, ≥ 3 mm float, ~20 mm manual height adjust, 7–16 mm pens |
| Pen pressure (start point) | ~20–80 g |
| Baseboard | 18 mm plywood, ~850 × 650 mm |
| Shaft spacing | 520 mm |
| Y belt | 30 mm outboard of each shaft; motor/idler axis ~27.8 mm above the baseboard; idler axle y 44, motor axis y 799 (machine frame); ~1.45 m belt per side |
| X belt | Vertical loop behind the beam, center 23 mm behind the beam's center plane; motor/idler axis ~94.8 mm above the baseboard; ~1.2 m belt |
| Carriage | Wheels 64 mm apart; front face 21.3 mm in front of the beam center; bottom 33.15, top 122.85 mm above the baseboard |
| Tool-plate interface | 50 W × 45 H, bottom edge at 33.15 mm; hook groove at the top; 2 × M3 inserts 36 mm apart |
| Mechanics footprint | ~600 × ~800 mm |

`python -m plotter_cad check` prints the current values from `params.py`.

---

## 6. As-built design notes

Dimensions and details of the parts designed so far. The principles behind them are in
README §3; the exact values live in `params.py`.

**Belt lines:** each Y side has its own belt **30 mm outboard of its shaft** (motor at
one end, idler at the other, ~1.4 m belt each). The top run is cut and both ends clamp
under the gantry end bracket; the belt line puts the Y motor shaft and idler axle at
**~27.8 mm** above the baseboard. The **X belt** is a vertical loop behind the beam (belt
center 23 mm behind the beam's center plane, ~1.2 m of belt); its top run is cut and
clamped under the carriage's rear block, ~3.6 mm above the beam top. X motor shaft and
idler axle run front-to-back at **~94.8 mm** above the baseboard.

**Y drive (T3.5):** per side, the motor sits **behind the rear SK10** with its shaft
pointing outboard (body inboard, ≥ 3 mm from the SK10; `y_motor_mount.py`: 5 mm plate, foot
extending outboard so the wood screws stay accessible, two gussets). The idler is **in front
of the front SK10** on an M5 axle held by an outboard plate (`y_idler_mount.py`): the axle
slides in an 8 mm slot along y, an M3 screw from the plate's rear edge pushes it forward
to tension, and the axle nut locks it (tension is set with the gantry moved back, since
the screw head sits just in front of the gantry's front stop). The **Y endstop**
board stands on a tower on the idler plate, in the plane of the bracket's trigger screw, front edge toward +y: the screw tip presses
the lever toward the board ~2.2 mm before the end of travel (the screw length sets the trip point). All
mounts are screwed down with M4 wood screws (assumed) through counterbored feet; the right-hand parts are mirror images, except the tower (the board is chiral).

**X drive (T3.4):** the **X motor** sits behind the beam at the right end
(`x_motor_mount.py`), the **idler + belt tensioner** at the left end (`x_idler_mount.py`:
the M5 axle slides in an 8 mm slot, an M3 screw pushes it outward, the axle nut locks it),
with the **X− endstop** on a pad on top of the idler mount (`x_endstop_mount.py`, ±4 mm slots; the board lies flat, the trigger head presses the lever along the board).
Both mounts sit on the gantry bracket over the rear SCS block and are clamped by that
block's 4 M5 bolts (M5×25 there instead of M5×20), so the brackets need no extra holes.

**Height stack-up (from the shaft mounting surface):** shaft center 20 mm → SCS10UU base
7 mm → SCS10UU top face **33.5 mm** (26.5 mm measured block height) → gantry end brackets
(4 × M5 into the block, 28 × 21 mm pattern) → beam. The carriage's bottom V-wheels hang
~22 mm below the beam, so the **beam bottom sits at ~58 mm** (bed top ~15, 15 mm media,
3 mm clearance, ~25 mm of carriage below the beam): the end brackets lift the beam
~25 mm above the SCS top face. Computed and checked in `params.py`; details in
[`docs/hardware.md`](docs/hardware.md).

**Gantry end brackets (T3.2, `parts/gantry_end_bracket.py`, left + mirrored right):**
a 10 mm base plate on both SCS blocks (8 × M5), a ribbed face plate the beam end bolts to
(2 × M5 into the beam's end bores, in a 1.5 mm locating pocket), the two Y-belt clamps
underneath (printed caps with tooth ridges, M3 into heat-set inserts), and an M3 trigger
screw for the Y endstop that also fine-tunes each side's home position. The **beam end
sits directly over the shaft**, so the gantry weight bears straight down on the blocks;
this sets the shaft spacing to **520 mm**. ~70 g each (PETG).

**Work area:**
- **X travel ≈ 426 mm** (520 mm beam − ~70 mm carriage − 2 × 12 mm end keep-out: in front
  of the beam the tool head can't pass over the SCS blocks).
- **Y travel ≈ 540 mm** (700 mm − 2 × 14 mm SK10 − ~120–135 mm gantry end).
- Footprint of the mechanics ~600 (X) × ~800 (Y) mm; Y motors/idlers set the Y length (T3.5).

**X carriage (T3.3, `parts/x_carriage.py`):** an 8 mm front plate with 4 V-wheels
64 mm apart: top pair on printed 8.3 mm stand-offs, bottom pair on the eccentric spacers
(D21), all on M5×35. A bridge over the middle of the beam (between the top wheels) carries
a rear block behind the beam that clamps both ends of the X belt (same clamp caps as Y) and
holds the X endstop trigger (M3 screw head, pointing −X). Printed front face down, ~64 g.

**v1 pen holder (planned, T3.6):** a printed body on the interface with a vertical slide
carrying a V-groove pen clamp (centers 7–16 mm pens on one axis; thumbscrew or strap), a
coarse ~20 mm height adjustment, and a mount for the servo (gravity + servo first).

---

## 7. Ideas and future possibilities

- **Automatic pen changing:** parking slots at the edge of the work area, or a carousel.
  The tool-plate interface and connector leave room for it.
- **Extrusion "spine" tool head** (e.g. the 340 mm 2040): not for v1, since the pen needs
  only a few mm of stroke and an extrusion adds mass and leverage. It could become its own
  tool head later for a heavy tool needing a long Z.
- **TFT35-E3 standalone plotting** from its SD/USB (T2.6).
- **Supported rails** (e.g. SBR12) in place of the Ø10 shafts if shaft sag ever shows up.
- **Other tool heads** (see README §1, non-goals for now).
