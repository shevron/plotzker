# Project status

The state of the ongoing development: where we are, what is next, open questions,
detailed decisions, inventory, key numbers, as-built design notes and ideas. Goals,
requirements, the high-level design and the coding standards are in
[`README.md`](README.md); references like "README §3.2" point there.

> **Status:** Phase 1 (architecture) complete. Phase 3 in progress: T3.1–T3.6 done (CAD
> scaffold, gantry end brackets, X carriage, X and Y motor/idler/endstop mounts, v1 pen
> holder); STLs in `stl/`, test prints pending. CAD migrated from OpenSCAD to PythonSCAD
> (T3.9, D22; identical STLs). On trial: SVG 2D sketches for profiles (D23), handles and
> `align()` (D28). Q12 answered (tap the second bore of each beam end). Q10 (SVG/PDF
> toolchain) deferred until the machine runs.
>
> **Next:** T3.7 full assembly and baseboard layout (T3.10 handle rollout can go first or
> alongside). Phase 2 can run in parallel.

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
  Also, for the Creality V4.2.2 fallback: MCU and driver chip markings, bootloader present
  (`docs/controller.md`). The final controller choice (Q1) is made after Phase 2.
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
    sizes, adjust at assembly. Eccentric spacers are available (Q11).
  - Remaining measurements moved to the tasks that need them (T3.2, T3.3/T3.5, T3.6).
- [x] **T3.2 Gantry end brackets (×2).** Bolt to two SCS10UU (4 × M5 each, 28 × 21 mm), hold
  the 4020 beam square, include the Y belt clamp and the Y endstop trigger. Lift the beam
  bottom to ~58 mm (§6). Bracket bears on the SCS10UU's two 10 mm top flats (measured).
  → `parts/gantry_end_bracket.py` (left/right), `parts/belt_clamp.py` (×4 for Y, ×2 for X),
  `assemblies/gantry.py`; STLs in `stl/`. The endstop switch itself mounts in T3.5.
  - [ ] Follow-up: test-print one bracket and check the fit
    on the SCS blocks, the beam pocket and the belt clamp before printing the pair.
- [x] **T3.3 X carriage.** 4 V-wheels on the 4020 (eccentric bottom pair, D21), X belt clamp,
  X endstop trigger, tool-plate interface (hook + 2 × M3), connector mount, cable strain relief.
  Eccentric spacers measured (10 mm hex × 7.8, Ø7 × 2.1 boss, ~0.7 mm offset): bottom wheels
  sit 8.3 mm from the plate face; the top wheels match on printed stand-offs.
  → `parts/x_carriage.py` 
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
  - [x] Endstop mount redone in T3.5 for the measured board (it had been modeled wrongly):
    the board now lies flat on a pad on the idler plate, the trigger screw head pressing the
    lever along the board's length. The idler plate top dropped to z 105.35 (derived).
  - [ ] Follow-up: test-print; check belt tension range and the switch trip point.
- [x] **T3.5 Y motor mounts, Y idlers and belt tensioners** (on the baseboard, in line with
  each shaft), and the Y endstops. Belt 30 mm outboard of each shaft; motor shaft /
  idler axle at `Y_AXIS.pulley_axis_z` (~26.8 mm). The X− endstop was done in T3.4.
  → `parts/y_motor_mount.py`, `parts/y_idler_mount.py` (each left + right, so 4 STLs; the
  endstop is a tower on the idler mount), `assemblies/y_drive.py` (also in the skeleton).
  The endstop board was measured with photos (M3, 15 mm pitch, switch across the front edge,
  lever hinged at the left, 1.5 mm board, connector 10 × 7.2 × 5.6 mm) and modeled in
  `hardware/endstop.py`; both endstop mounts (X and Y) follow it. The board is chiral, so
  the right-hand Y idler mount isn't a pure mirror image (the tower's height differs).
  Both mounts also have an SK10 pocket (D26; tested: the SK10 seats in the corner and the other sides are open).
  Each connector has a 15 mm plug keep-out behind it (tests: nothing intrudes); it pushed
  the Y idler forward (axle y 32) and moved the trigger contact 4 mm in from the lever tip.
  Checked: no collisions with the gantry, SK10s or shafts at the front, middle or back of
  Y travel (test); only the trigger pressing the endstop lever.
  - [ ] Follow-up: test-print; check the pocket corner against an SK10 and the
    belt tension range, and the trip point (adjust with the
    trigger screw length); measure where the switch clicks (modeled at 75 % of the lever's
    travel) and check the board's assumed body offset (2.5 mm right of center) and lever
    length (13.5 mm); check that a plug fits on the connectors; check the idler plate against
    the wood-screw positions; measure the SK10 bore offset from the base edges (it limits
    belt parallelism).
- [x] **T3.6 v1 pen holder (tool head).** Gravity-loaded pen slide on a Ø6 rod in two
  printed sleeves, lifted by an FT90M servo (D29); V-block + M5 thumbscrew clamp for 7–16 mm
  pens; the pen's position in the clamp is the ~20 mm height adjustment.
  → `parts/pen_holder_body.py` (hook lip, 2 × M3, rod arms, servo wall, key rib) and
  `parts/pen_slide.py` (sleeves, V-block, yoke, lug with the pin slot);
  `assemblies/pen_holder.py` (fit check with the carriage, pen up and down; pens Ø7, Ø10, Ø16:
  no collisions); design checks in `params.design_checks()`; STLs in `stl/`.
  - [ ] Follow-up: test-print both parts. Check the sleeve fit (ream the bores to 6.2 mm) and
    friction, the key groove, the horn pin (M2 into a horn hole: check the hole diameter) and
    the servo pilot holes (Ø1.6, *assumed*). Measure the slide's mass and tune the pressure
    (20–80 g): the slide has no weight pocket yet, so add one (e.g. M5 washers on a screw) if
    the slide plus pen is too light. Measure the horn thickness and the spline height
    (*assumed* 1.8 / 3 mm), and the actual slide-to-pen stiffness (pen cantilevers ~30 mm
    below the clamp). If the printed sleeves stick, use LM6UU bearings or brass-tube bushings.
  - [ ] Follow-up: cable route from the servo to the carriage connector window; limit angles
    and `M280` values (T2.4) for ±23° about horizontal; pen holder on the gantry at both ends
    of travel (T3.7).
- [ ] **T3.7 Full assembly and baseboard layout.** Assembly model for fit checks (travel,
  clearances, 15 mm media under the head). 1:1 baseboard drilling layout: SK10 positions,
  motor mounts, bed-panel adjustment points, runners, electronics.
- [ ] **T3.8 Cable management.** Drag chain or cable guide from the gantry to the board.
- [x] **T3.9 Migrate the CAD to PythonSCAD (D22).** Sanity test: PythonSCAD renders the
  old `.scad` files to the same STLs. Port to a Python package (`src/plotter_cad/`:
  `params.py`, `hardware/`, `parts/`, `assemblies/`, `build.py` CLI) with pytest tests
  and ruff. Checked: all 8 STLs geometrically identical to the OpenSCAD ones (volume,
  bounding box, cross-sections); assemblies match by
  volume and bounding box; same key numbers. The old `.scad` files were removed afterwards.
- [ ] **T3.10 Roll out handles (D28).** Add handles to the other parts and use `align` in `assemblies/` (Y drive mounts, X carriage, X mounts, the pen holder (servo, rod, screws are placed from `params.PenHolder`), endstop frames: `place_in_frame` is a hand-rolled handle; mind the chiral, mirrored endstop board). *Done when:* no assembly re-derives a hole position that a part defines; geometry unchanged.

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
| Q1 | Controller boards | 🔬 ZRIB v5.8 primary; Creality Ender 3 V4.2.2 fallback (compared in `docs/controller.md`); **final decision after T2.x**. TFT35-E3 is a screen/SD sender |
| Q2 | Parts inventory | ✅ Enough to proceed; remaining measurements listed in the tasks (T2.1, T3.1) |
| Q3 | Work area, rail length, media thickness | ✅ A3; ~540 mm Y travel; 0–15 mm media |
| Q4 | Cartesian vs CoreXY | ✅ Cartesian |
| Q5 | Gantry drive and squaring | ✅ Dual Y motors + dual endstops |
| Q6 | Pen lift and thickness handling | 🔬 Approach decided; mechanism chosen by experiment (T6.2) |
| Q7 | Firmware and board mapping | ✅ Marlin `BOARD_ZRIB_V53`; verified in T2.3 |
| Q8 | Tool-plate interface and v1 pen holder | ✅ README §3.4 |
| Q9 | Frame, baseboard and work holding | ✅ README §3.8 (bed material finalized at build) |
| Q10 | SVG/PDF → G-code toolchain | ⏸ Deferred to phase 7 |
| Q11 | X-carriage wheel preload | ✅ D21: 2 eccentric spacers on the bottom pair (available; no fallback) |
| Q12 | Are the 4020 beam ends tapped M5 (gantry brackets bolt into the end bores)? | ✅ Yes: all beam end bores are tapped M5 (done by the user) |

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
| D21 | X-carriage preload: 2 eccentric spacers on the bottom wheel pair (available; the slot fallback was dropped) | ✅ | README §3.4, Q11 |
| D22 | Migrate the CAD from OpenSCAD to PythonSCAD: a `plotter_cad` Python package (`src/`), pip `pythonscad` module for STL export, PythonSCAD app for renders/preview. Ported 1:1 (all 8 STLs geometrically identical); the old `.scad` files were removed afterwards. D2 originally named OpenSCAD | ✅ | README §6, T3.9 |
| D23 | **Experiment:** 2D sketches as SVG files next to the module that extrudes them (sketch → extrude workflow), loaded with `geometry.load_sketch()`. First use: the V-slot 2020/2040 profiles (`hardware/vslot_2020.svg`, `vslot_2040.svg`). PythonSCAD stays the only 3D source; printable parts stay fully parametric in Python for now | 🔬 Trial | README §6 |
| D24 | Parametric sketch formats researched (`docs/sketch-formats.md`): no open interchange format carries sketch constraints. A Python constraint-sketch module (python-solvespace) was tried on the 2020 profile and **rejected**: it doesn't allow GUI drawing and adds little over plain PythonSCAD. **Stay with SVG (D23)**: designers draw and constrain in their CAD tool (e.g. FreeCAD) and export SVG. Revisit: automate the export with FreeCAD as a dependency | ✅ | `docs/sketch-formats.md` |
| D25 | Y drive layout: motor **behind the rear SK10**, shaft outboard, belt 30 mm outboard of the shaft; idler with slot tensioner in front of the front SK10; Y endstops at the **front** on both sides, on a tower of the idler mount; printed mounts screwed to the baseboard with M4 wood screws (*assumed* size). Costs ~25 mm of baseboard length at the back; belt ~1.5 m per side | ✅ | T3.5, §6 |
| D26 | The Y motor and idler mounts have a **corner pocket for their SK10** (cut-out in a 6 mm foot: a 24 mm end-wall finger against the shaft-end face and an outboard side wall; open toward the inboard side and the other SK10; the finger is kept short so it stays sturdy), so the belt line is referenced to the SK10's outer face and outboard edge instead of the baseboard layout and SK10 width/chamfer tolerances don't matter. Mounts are fitted last, around the already aligned SK10s, pushed into the corner, and screwed down through plain holes (no pre-drilled positions). The SK10's own bore tolerance limits the result | ✅ | README §3.2, T3.5 |
| D27 | Belt clamps: flat undersides on the gantry brackets and the X carriage's rear block (no belt channel: no bridges or overhangs); one cap design for all six clamps, with the groove (between two rails) and the tooth ridges in the cap. Belt lines drop 1.08 mm (derived); screws M3×12 | ✅ | T3.2, T3.3, §6 |
| D28 | **Handles and `align()` for assemblies (trial).** Parts that hardware or other parts attach to expose named handles (4×4 matrices set with `geometry.set_handles`, read with `get_handle(s)`); assemblies place the hardware with `.align(handle)` instead of re-deriving hole coordinates, and the part's own cut-outs use the same handle constants, so a hole and its screw can't drift apart. Done for the gantry end bracket and the belt clamp; extend to other parts as they are touched. `fillet` and `MultiToolExporter` evaluated and not adopted yet | ✅ trial | README §7.4, T3.10 |
| D29 | **v1 pen holder (T3.6):** one Ø6 rod (on hand) held by two printed arms; the pen slide rides on it in two printed sleeves (LM6UU is the later upgrade; the bores are laid out for it); a key rib on the plate, in a groove of the slide's lug, stops it turning. The FT90M (metal gears; chosen over the FS90) lies with its output facing the plate and the single-sided horn swinging in the gap behind its wall; the horn's M2 pin sits in a vertical slot of the lug, whose ceiling lifts the slide (pin down: the slide drops until the pen touches, the slot clearance is the float). Pen: 90° V-block with a yoke and an M5 thumbscrew; pen axis 16–22 mm in front of the carriage face. Rejected: flexure/four-bar (pressure not constant, long reach), plastic dovetail (stick-slip). Alternate if the sleeves stick: 625-bearing roller guide | ✅ | T3.6, §6 |
| D29 | **No heat-set inserts: pressed-in hex nuts (nut traps) everywhere.** The nut sits in a slot or hex shaft with a wall behind it that takes the load (`TOL.nut_wall`, 2 mm). Y/X idler tension screws: slot from the top; X endstop pad screws: slots from the rear face; belt clamp screws (brackets): hex shafts from the top, nut 4 mm above the underside (`CLAMP.nut_z`), M3×14; X carriage rear block: slot from the back; tool-plate screws: slots from the bottom edge. Dropped the `Preload.SLOT` carriage fallback (eccentric spacers are available) | ✅ | README §7 rule 2 |

---

## 4. Inventory (parts on hand)

Working assumption: any **commonly available** 3D-printer / maker part can be obtained.
Parts listed here are ones we specifically plan around. If something turns out to be
hard to get, we adjust.

| Part | Qty | Details | Still to confirm |
|------|-----|---------|------------------|
| 2020 V-slot extrusion | several | **520 mm** long | — |
| 4020 V-slot extrusion | 2 | **520 mm** long → X beam; V-slot profile confirmed | End bores tapped M5 |
| Shorter 2020 / 2040 / 4040 extrusions | assorted | e.g. 340 mm 2040 → baseboard runners/feet | Lengths |
| V-wheels | many | POM V-groove wheels on 625Z bearings (5 mm bore), Ø24 × 10 mm; eccentric spacers: 10 mm hex × 7.8, Ø7 × 2.1 boss, Ø5 bore, ~0.7 mm offset (2 needed, D21) | — |
| Ø10 mm smooth (optical-axis) shafts | 2 | **700 mm**, hardened → Y axis | — |
| SK10 shaft supports | 4 | End supports, shaft center **20 mm** above the mounting surface; 2 × M5 on 32 mm, 42 W × 37.5 H × 14 L ([`docs/hardware.md`](docs/hardware.md)) | — |
| SCS10UU linear bearing blocks | 4 | 2 per shaft; 35 L × 40 W × 26.5 H mm, shaft center 13 mm above the base, 4 × M5 top holes on 28 × 21 mm, top: two 10 mm raised flats (holes in them) with a 17 mm × 1 mm recess between, 92 g ([`docs/hardware.md`](docs/hardware.md)) | — |
| NEMA17 stepper motors | ≥ 3 (+1 for optional Z) | Standard 3D-printer type; sizes vary: typical 39.2 mm body / 22.6 mm shaft, short 33.5 / 19 | — |
| GT2 belt, pulleys, idlers | assorted | 6 mm belt (plenty); common 3D-printer 20T pulleys and idlers | Exact pulley/idler sizes (design for common, adjust) |
| Lead screws, linear bearings, misc. bearings | assorted | No LM6UU/LM8UU found yet | Only needed for a stepper Z experiment or the pen slide upgrade |
| Ø6 rod | 1 | ~200 mm, cuttable; the pen holder's rod needs 63 mm | — |
| Hobby servos | 2+ | **FeeTech FT90M** (metal gears, digital; used for the pen lift) and FS90 (spare); measured in `docs/hardware.md` | Horn thickness, spline height |
| **Controller: Zonestar ZRIB v5.8** | 1 | ATmega2560, 6 socketed StepStick drivers ([`docs/controller.md`](docs/controller.md)) | Driver chip type; pin map (bench) |
| Controller: Creality Ender 3 V4.2.2 | 1 | STM32F103, 4 soldered drivers (X, Y, Z, E0), 3 endstop inputs + probe pin, 24 V; fallback ([`docs/controller.md`](docs/controller.md)) | MCU and driver chip markings; bootloader; PSU voltage |
| BigTreeTech TFT35-E3 | 1 | Touch screen with its own MCU; **not a motion controller**. Optional UI and SD/USB G-code sender | Hardware version |
| Power supply | 1 | From a printer | **Voltage (12/24 V), current** |
| Endstop switches | ≥ 3 | Creality-type boards: 20 × 19 × 1.5 mm, M3 holes 15 mm apart at the rear, switch across the front edge, lever 5 mm out at rest / 1.5 mm pressed, connector 10 × 7.2 × 5.6 mm with 2 mm past the rear edge (`docs/hardware.md`) | Click point, lever length |
| Plywood, steel sheet, magnets | to buy/cut | Baseboard, bed panel, work holding (README §3.8) | — |

---

## 5. Key numbers (quick reference)

| Item | Value |
|------|-------|
| X travel / Y travel | ~426 mm / ~545 mm |
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
| Y belt | 30 mm outboard of each shaft; motor/idler axis ~26.8 mm above the baseboard; idler axle y 31, motor axis y 800 (machine frame); ~1.5 m belt per side |
| X belt | Vertical loop behind the beam, center 23 mm behind the beam's center plane; motor/idler axis ~93.8 mm above the baseboard; ~1.2 m belt |
| Carriage | Wheels 64 mm apart; front face 21.3 mm in front of the beam center; bottom 33.15, top 122.85 mm above the baseboard |
| Pen holder | Lift 7 mm / float 3 mm; rod Ø6 × 63 mm; slide 45 mm; pen axis 16–22 mm in front of the carriage face; head depth ~39 mm (servo front), up to z ~105 |
| Tool-plate interface | 50 W × 45 H, bottom edge at 33.15 mm; hook groove at the top; 2 × M3 nuts 36 mm apart |
| Mechanics footprint | ~600 × ~800 mm |

`python -m plotter_cad check` prints the current values from `params.py`.

---

## 6. As-built design notes

Dimensions and details of the parts designed so far. The principles behind them are in
README §3; the exact values live in `params.py`.

**Belt lines:** each Y side has its own belt **30 mm outboard of its shaft** (motor at
one end, idler at the other, ~1.4 m belt each). The top run is cut and both ends clamp
under the gantry end bracket; the belt line puts the Y motor shaft and idler axle at
**~26.8 mm** above the baseboard. The **X belt** is a vertical loop behind the beam (belt
center 23 mm behind the beam's center plane, ~1.2 m of belt); its top run is cut and
clamped under the carriage's rear block, 2.5 mm above the beam top. X motor shaft and
idler axle run front-to-back at **~93.8 mm** above the baseboard.
**Belt clamps (D27):** one cap design (`belt_clamp.py`) for all six clamps. The gantry
brackets and the carriage's rear block have **flat undersides** (no printed channel or
bridge); the cap has the groove (between two 1.08 mm rails) that guides the belt, ridges in
the tooth gaps, and M3×14 screws into M3 nuts pressed into the bracket / block (hex shafts from the top on
the brackets, a slot from the back on the carriage).
**Handles (D28):** the gantry end bracket exposes `block_bolts_front_0..3`, `block_bolts_rear_0..3`, `beam_bolts_0..1`, `belt_clamps_0..1` (front, rear) and `trigger_screw`; the belt clamp exposes `mount` (rail tops). `gantry_end_local` aligns the screws, clamps and belt pieces to them. PythonSCAD carries a handle through `translate`, `mirror` and boolean operations, but only if it is a matrix attribute (not a list of them; hence the numbered names) and not through `fillet`.

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
Each mount's foot also carries an **SK10 pocket** (`parts/sk10_pocket.py`, D26): a corner cut-out the
SK10's base sits in (4 mm × 24 mm end-wall finger against the shaft-end face, outboard side wall; open
toward the inboard side and the other SK10), so the mounts are fitted last, pushed into the corner of
the aligned SK10s.

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
underneath (printed caps with a belt groove and tooth ridges, M3×14 into pressed-in
nuts), and an M3 trigger
screw for the Y endstop that also fine-tunes each side's home position. The **beam end
sits directly over the shaft**, so the gantry weight bears straight down on the blocks;
this sets the shaft spacing to **520 mm**. ~70 g each (PETG).

**Work area:**
- **X travel ≈ 426 mm** (520 mm beam − ~70 mm carriage − 2 × 12 mm end keep-out: in front
  of the beam the tool head can't pass over the SCS blocks).
- **Y travel ≈ 545 mm** (700 mm − 2 × 13.1 mm SK10 − ~125 mm gantry end − 2 × 2 mm margin).
- Footprint of the mechanics ~600 (X) × ~800 (Y) mm; Y motors/idlers set the Y length (T3.5).

**X carriage (T3.3, `parts/x_carriage.py`):** an 8 mm front plate with 4 V-wheels
64 mm apart: top pair on printed 8.3 mm stand-offs, bottom pair on the eccentric spacers
(D21), all on M5×35. A bridge over the middle of the beam (between the top wheels) carries
a rear block behind the beam that clamps both ends of the X belt (same clamp caps as Y) and
holds the X endstop trigger (M3 screw head, pointing −X). Printed front face down, ~64 g.

**v1 pen holder (T3.6, D29):** two printed parts. The **body** (`pen_holder_body.py`) is a
50 × 45 mm plate with the hook lip (the carriage groove shrunk by the 0.3 mm gap) and
2 × M3 counterbored holes, a spine up to z ~105, two arms that hold the Ø6 rod (lower: blind
seat; upper: through), a key rib, and a wall with a 12.4 × 23.5 mm window for the FT90M (tabs
rest on the wall's front, M2-class self-tapping pilot holes; outer rib and two webs). Printed on its
left side. The **slide** (`pen_slide.py`) is a 45 mm column with two 13 mm sleeves (relief
between), a 90° V-block (apex 11 mm from the carriage face; pens 7–16 mm sit with the axis
16–22 mm out), a yoke with an M5 nut pocket and thumbscrew pressing the pen into the V, and a
lug with the pin slot and key groove. Printed back face down. Travel: lift 7 mm, float 3 mm
(pin travel 10 mm; horn ±23° about horizontal at the second hole, r = 12.6 mm), rod 63 mm.
Dimensions: `params.PenHolder` (head frame: x across, d forward from the carriage face, z
absolute). The pen's height is set by sliding it in the clamp.

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
