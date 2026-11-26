# Project status

The state of the ongoing development: where we are, what is next, open questions,
detailed decisions, inventory, key numbers, as-built design notes and ideas. Goals,
requirements, the high-level design and the coding standards are in
[`README.md`](README.md); references like "README §3.2" point there.

> **Status** (2026-11-26): the **X axis is built and works** on the bench (Creality V4.2.2,
> D41): all printed X parts are tested, it homes and travels (T2.7). The rest of the mechanical
> CAD for v1 is designed; open are the X cable (T3.8), the PSU hood and brackets (T3.31) and a
> controller mount for the new board (T3.32). The Y drive parts and the pen holder are not yet
> test-printed and checked.
>
> **Next:** print and check the Y motor and idler mounts and build both Y assemblies, then
> bring up Y/Y2 (T2.2, T2.3, T2.5). The servo test (T2.4), the X cable mock-up (T3.8) and the
> baseboard (T4.1) can go on in parallel.

**Contents:** 1 Work plan · 2 Open questions · 3 Decision log · 4 Inventory ·
5 Key numbers · 6 As-built design notes · 7 Ideas and future possibilities

---

## 1. Work plan

### Build phases

| Phase | Name | Output | Status |
|-------|------|--------|--------|
| 0 | Inventory & requirements | README §2, §4 | ✅ Done |
| 1 | Architecture decisions | README §3, §4 | ✅ Done |
| 2 | **Electronics bench bring-up** | Marlin configured and flashed; pin map verified; motors, endstops and servo working on the bench | 🔧 X axis done |
| 3 | **Mechanical CAD (PythonSCAD)** | Parametric model: gantry, carriage, mounts, v1 pen holder, baseboard layout | 🔧 In progress |
| 4 | Print & assemble | Baseboard, Y axis, gantry, X axis, wiring | X parts printed |
| 5 | Integration & calibration | Homing, squaring, steps/mm, soft limits, bed leveling | — |
| 6 | First plots & pen-lift experiments | Test patterns from hand-written/scripted G-code; pen-lift mechanism chosen (Q6) | — |
| 7 | Software toolchain | SVG/PDF → G-code workflow (Q10) | Deferred |
| 8 | Enhancements | Automatic pen change, other tools, TFT35 standalone use | — |

Phases 2 and 3 are independent and can run in parallel.

Tasks are sized for one working session each; what to do when one is finished is in README
§7.1. Finished tasks are kept as one line; their details are in git history, the decision log
(§3) and the as-built notes (§6).

### Phase 2 — Electronics bench bring-up (see `docs/controller.md`)

- [ ] **T2.1 Read the hardware facts.** PSU, MCU, driver markings and servo model are recorded;
  left: the drivers' factory Vref.
  *Done when:* recorded in `docs/controller.md`.
- [ ] **T2.2 Configure Marlin.** The X-axis settings are done (`firmware/apply_config.py`,
  [`firmware/README.md`](firmware/README.md)). Left: `Y_DUAL_STEPPER_DRIVERS`,
  `Y_DUAL_ENDSTOPS` (+ `Y2_USE_ENDSTOP` on Z−), `NUM_SERVOS 1`, SD card support, Y driver
  checks. *Done when:* the full configuration compiles (`STM32F103RE_creality`).
- [ ] **T2.3 Flash and verify the pin map.** Flashing and the X driver and endstop are verified.
  Left: Y and Y2 (the E driver drives Y2), the Y endstops (`M43 W` / `M119`).
  *Done when:* the pin map in `docs/controller.md` is marked verified, or corrected.
- [ ] **T2.4 Servo and 5 V test.** Servo on the `BL_T` header (G, V, OUT). Check `M280 P0 S<angle>`
  sweeps, and that the board doesn't reset with the servo stalled.
  *Done when:* header and angle range recorded; decision on a separate 5 V supply.
- [ ] **T2.5 Driver current (Vref).** X is set (0.88 V). Left: Y and Y2, both identical.
- [ ] **T2.6 (Optional) TFT35-E3.** Make an adapter from the board's LCD connector (UART3) and
  connect the TFT in touch mode.
- [x] **T2.7 X-axis bench bring-up** (2026-11-26): the carriage homes (ten homings within
  0.1 mm) and travels to X = 410. Guide: [`docs/x-axis-bringup.md`](docs/x-axis-bringup.md);
  results: [`docs/controller.md`](docs/controller.md).

### Phase 3 — Mechanical CAD (PythonSCAD; conventions in CODING_STANDARDS.md, workflow in README §6)

Done:

- [x] **T3.1** CAD scaffold: `params.py`, vendor hardware models, design checks.
- [x] **T3.2** Gantry end brackets. Print-tested.
- [x] **T3.3** X carriage. Print-tested (the tool-plate hook fit is checked with T3.6).
- [x] **T3.4** X motor mount, X idler and X endstop. Print-tested.
- [x] **T3.5** Y motor mounts, Y idlers, belt tensioners and Y endstops (print test open, see
  below).
- [x] **T3.6** v1 pen holder (D37; print test open, see below).
- [x] **T3.7** Full assembly, ZRIB mount and 1:1 baseboard drilling layout (D30, D31).
- [x] **T3.9** CAD migrated from OpenSCAD to PythonSCAD (D22).
- [x] **T3.10** Handles and `align()` rolled out to the assemblies (D28).
- [x] **T3.11–T3.14** Fixes after the first X prints: motor mount bolt heads counterbored,
  hex-profile nut slots, one slot per belt clamp nut, endstop solder relief and a shorter
  trigger screw. Tested on X.
- [x] **T3.15–T3.17** Dovetail belt tensioners: superseded by the floating idlers (D42).
- [x] **T3.18** FEM check tooling and the `fem-analyst` sub-agent ([`docs/fem.md`](docs/fem.md)).
- [x] **T3.19** Shelf under the left bracket's idler side (D35).
- [x] **T3.20** Design diff tool (`python -m plotzker diff`).
- [x] **T3.21** Tensioner tilt under belt load: found by an assembly FEM check, fixed by T3.22
  and T3.23.
- [x] **T3.22** Floating X idler on a tower in the left bracket (D42). Tested.
- [x] **T3.23** Floating Y idlers (D42; print test open, see below).
- [x] **T3.24** CAD split into `cadder` and `plotzker` (D36; revert point `pre-cadder-split`).
- [x] **T3.25** Nut pocket tolerances retuned on prints; prototype parts removed.
- [x] **T3.26** One `idler_slider` for all three idlers. Print-tested.
- [x] **T3.27** CPSK sketch format: draft spec and reader (`cadder/docs/cpsk/`). Follow-ups: a
  command-line tool and the spec's open issues (Appendix A). Using `.cpsk` files as plotter CAD
  sources is not decided (it would change D23/D24 and README §7.1).
- [x] **T3.28** CPSK FreeCAD addon. Follow-ups: Addon Manager release, ellipses and B-splines.
- [x] **T3.29** Photo measurement tried; use the caliper (D39).
- [x] **T3.30** Endstop board length corrected (20.3 mm); blank renders fixed.

Open:

- [ ] **Y drive test print** (follow-ups of T3.5, T3.14, T3.23, T3.30). Print the current Y
  motor mounts, Y idler mounts and two `idler_slider`s, and check:
  - the SK10 sits in the pocket corner; measure the SK10 bore offset from the base edges (it
    limits belt parallelism);
  - belt tension range and the floating idlers on both ends;
  - Y endstops: trip point (set by the trigger screw length), where the switch clicks
    (*assumed* at 75 % of the lever travel), plug fit;
  - the mounts' feet and wood-screw positions on the baseboard.
- [ ] **Pen holder test print** (follow-ups of T3.3, T3.6). Print `pen_holder_body` and
  `pen_slide`, and check: hook-groove fit on the carriage; sleeve fit (ream to 6.2 mm) and
  friction; key groove; the horn's M2 pin; servo pilot holes (Ø1.6, *assumed*); horn thickness
  and spline height (*assumed* 1.8 / 3 mm); slide mass and pen pressure (20–80 g; the slide has
  no weight pocket yet); slide-to-pen stiffness. If the sleeves stick, use LM6UU bearings or
  brass-tube bushings. Then: servo cable route to the carriage connector window, and the limit
  angles and `M280` values (±23° about horizontal, with T2.4).
- [ ] **Open FEM verdicts** (`make fem-status`). The user will re-analyze these; some parts
  still need testing and changes. None is accepted:
  - `gantry_end_bracket_left` FAIL (the tower seat's vertical movement at belt peak, over its
    0.1 mm limit) and `x_motor_mount` FAIL (the motor plate bends under the belt pull); both
    printed parts work in the X-axis tests;
  - `y_motor_mount_left` FAIL (same plate bending), not yet printed and tested;
  - `pen_holder_body` MARGINAL (sideways knock), not yet printed and tested.
  `idler_slider` MARGINAL is accepted after its print test; `psu_bracket` is under T3.31.
  `belt_clamp` has no FEM spec (to decide). *Done when:* each verdict is accepted or the part is
  changed.
- [ ] **T3.8 Cable management** (D32: loose loom on printed rails). Moving cables: X motor and X
  endstop (move in Y), pen servo (moves in X and Y). The Y motors and endstops are static.
  - [ ] **Loom spec** (the user builds it to this; values *assumed* until it exists). Gantry
    loom: 10 conductors (X motor 4 at 24 AWG or thicker, ~1.5 A; X endstop 3; pen servo 3; the
    last two may be 26–28 AWG). Finished outer diameter **≤ 8 mm**, flexible wire, bend radius
    **≤ 16 mm**. About **1.1 m** from the controller to the gantry anchor (cut at build); about
    **0.5 m** from the carriage to the beam end (servo and endstop only, 15 cm spare). Keep each
    device's plug at the device end and use one inline connector at the gantry anchor, so the
    gantry can be taken off.
  - [x] Y loom modeled (`params.LOOM`, `parts/loom_anchor.py` ×1, `parts/loom_rail.py` ×6,
    `assemblies/loom.py`): anchor on the right bracket, loom drops to the baseboard, folds in a
    U beside the right Y belt and goes through a Ø12 hole at (690, 150). Rails are laid out by
    tape. The run to the controller changes with T3.32.
  - [ ] **X cable mock-up** (D33, user, before any CAD): a ribbon festoon in the beam's two rear
    T-slots; the fixed run lies in the lower slot, a free U (R ~10) outside the face returns it
    in the upper slot to a printed shoe on the carriage's rear block. Ribbon: flat,
    silicone-insulated, 6 conductors (28–30 AWG), **≤ 1.2 mm thick, ≤ 7.5 mm wide**, ~0.7 m
    (slot cavity 12 × 6.1 mm behind a 6.2 neck). On a spare 520 mm offcut: (1) lay 0.3 m in one
    slot and form the U; (2) push and pull the free end over ~200 mm at ~100 mm/s (the upper run
    is pushed when the carriage moves left): does it buckle, drag or snag; (3) 1000 cycles, then
    check insulation and continuity. Report pass / buckles / drags and the ribbon's size and
    bend radius.
    Fallbacks: flat ribbon in the 10 mm gap behind the beam; X travel cut to ~350 mm; a short
    drag chain on a tray. Rejected: sleeve behind the beam (droops), U fold on the beam top (no
    room), take-up pulley (cord force varies too much over 213 mm, needs a new anchor tower).
  - [ ] Test-print the loom anchor and one rail: zip tie path, nut slots, the loom seating in
    the groove, real loom diameter and bend radius.
- [ ] **T3.31 PSU mount and terminal hood** (D38): `parts/psu_bracket.py` ×2,
  `parts/psu_hood.py`, `hardware/psu.py`, `assemblies/psu_mount.py`, `params.PSU_MOUNT`.
  - [x] Hood redesigned after the first print; the XT60 press fit is approved on test pieces
    (7.4 mm proud).
  - [x] FEM of `psu_bracket`: **accepted by the user, print as is.** Agreed limits: 0.5 mm under
    the PSU's weight, 1 mm if leant on. Last result: weight 0.18 mm, leant on 0.71 mm, official
    verdict INCONCLUSIVE (mesh convergence 5.8 % vs 5 %), abuse strength 0.93–1.09 at the flange
    fillet. If more margin is wanted: flange 9 → 11 mm with 4 × 30 screws. `fem --viz` crashed
    on this part (KeyError in cadder's FEM visualization).
  - [ ] Reprint the hood: fit on the case (0 clearance; −0.05 if loose), the 48 mm inlet bridge,
    wire room behind the XT60 and inlet (hot glue behind the XT60 only if plugging in pushes it
    back).
  - [ ] Test-print a bracket.
  - [ ] Ease the baseboard's lower right edge 1 mm × 45° at the brackets (y 340–368 and 490–518)
    for their corner fillet.
  - [ ] Measure the inlet's push-on tabs (9 mm *assumed*) and flange flats (32 *assumed*).
  - [ ] Before closing the hood: set the output voltage (the ADJ pot gets covered), set the
    115/230 V selector to 230 V, fit a T3.15 A slow-blow fuse.
- [x] **T3.33 ZRIB code moved to `plotzker.legacy.zrib`** (2026-11-26, D43): out of the machine,
  FreeCAD assembly, registries and drilling layout; the PSU mount and loom are unchanged.
- [x] **T3.34 Readable names** (2026-11-26, CODING_STANDARDS.md §1): constants used by name, hardware specs
  suffixed `_SPEC`, abbreviations spelled out. Names in TOML files, `--json`, the CLI and CPSK kept.
- [x] **T3.35 Disallowed nested functions removed** (2026-11-26, CODING_STANDARDS.md §2): 23 nested functions
  remain, all allowed cases.
- [ ] **T3.36 Polymorphism instead of type checks** (CODING_STANDARDS.md §2). Behavior that depends on an object's class,
  or mainly works on its data, becomes a method of the class. A method must not pull a higher
  layer into the class (solver, exporter, renderer, CLI): code there keeps dispatching on type,
  with `match` instead of `isinstance` chains.
  1. Part hierarchy (`part.py`, `report.py`, `fem/report.py`): `part_to_dict` → `Part.to_dict()`,
     extended by `MaterialPart` and `PrintedPart`; the two part reports and the STL export become
     methods; `effective_properties` moves into the classes, `PrintedPart` supplying its factors.
  2. `Placement.region()`: `Box` and `Cylinder` place themselves.
  3. Each sketch primitive gets a `coordinates` property, replacing the chain in
     `import_sketch._geometry`.
  4. `assembly_to_dict` → `AssemblyCheck.to_dict()`; `write` / `save` → methods of `Document`.
     Candidates to read first: helpers taking a `Rectification`, `Board`, `Scale` or diff record.

  Stays as it is: load handling in `fem/applied.py`, the SVG and FreeCAD exporters' dispatch on
  sketch geometry (`cpsk_core` must not know them), validation of outside input.

  *Done when:* `make check`, `make test` and `make test-cpsk-core` pass; `part --json` output is
  identical for every part; `fem-status` shows nothing newly stale; `diff` shows no change.
- [ ] **T3.32 Controller mount for the Creality board** (D41). The machine has no controller mount
  and the drilling layout no holes for one; the ZRIB's mount is in `legacy/zrib/` (D43). The loom
  run, the PSU's XT60 position (D38) and `BASEBOARD.controller_center` were designed around the
  ZRIB: revisit them. Measure the Creality board first (outline, holes, height, connector
  positions); check that the USB cable can reach it.

### Phase 4 — Build

- [ ] **T4.1** Cut the baseboard and bed panel; fit the runners; drill from the T3.7 layout
  (holes for the controller wait for T3.32). Check the T-nut thickness and slot lip (*assumed*
  4 / 1.8 mm), the Ø2.5 pilot holes in your plywood, and the bed panel's sag between its four
  posts (est. 0.2–0.4 mm; add a center post if it shows).
- [ ] **T4.2** Mount the SK10s and shafts; fit the gantry; align the shafts (README §3.2).
- [ ] **T4.3** Fit the beam, carriage, motors, belts and endstops; check that the axes move
  freely by hand.
- [ ] **T4.4** Mount the electronics and PSU; wire everything; safety checks on mains wiring.

### Phase 5 — Integration & calibration

- [ ] **T5.1** First homing (Y squaring, then X); set soft limits from the measured travel.
- [ ] **T5.2** Steps/mm check (draw/measure a 300 mm line); squareness check (diagonals of a
  large square); belt tension.
- [ ] **T5.3** Bed leveling (README §3.8); set the pen-down height and the float.

### Phase 6 — First plots & pen-lift experiments

- [ ] **T6.1** Test-pattern G-code in `software/test-patterns/` (squares, circles, grids,
  text, pen up/down stress test); speed/acceleration tuning.
- [ ] **T6.2** Pen-lift experiments (Q6): gravity + servo, then spring + servo and
  solenoid/magnet options; compare pressure consistency, line quality and speed; record the
  results in `docs/pen-lift.md` and choose a mechanism.
- [ ] **T6.3** Registration corner (README §3.8).

### Phase 7 — Software toolchain (Q10)

- [ ] **T7.1** Choose and document the SVG/PDF → G-code workflow.

### Phase 8 — Enhancements (backlog)

- Automatic pen changing; TFT35 standalone plotting; other tool heads (see §7).

---

## 2. Open questions

| ID | Question | Status |
|----|----------|--------|
| Q6 | Pen lift and thickness handling | 🔬 Approach decided (README §3.3); mechanism chosen by experiment (T6.2) |
| Q10 | SVG/PDF → G-code toolchain | ⏸ Deferred to phase 7 (D20) |
| Q13 | Under-board space and mount for the controller | 🔬 To redo for the Creality board (T3.32) |

Answered, and recorded where the answer lives: Q1 controller (D41), Q2 inventory (§4), Q3 work
area (README §2, §3.2), Q4 kinematics (D5), Q5 gantry squaring (D13), Q7 firmware (README §3.5),
Q8 tool plate and pen holder (README §3.4, D37), Q9 frame and bed (README §3.8), Q11 wheel
preload (D21), Q12 beam end bores (all tapped M5).

---

## 3. Decision log

Detailed and in-progress decisions. The high-level decisions (D1–D10, D12–D16, D18, D19)
are in README §4; IDs are shared and never reused. To change a decision, propose it and
update the log once it is agreed (README §7.1). 🟡 = to be confirmed at build; 🔬 = trial.

| ID | Decision | Status | Ref |
|----|----------|--------|-----|
| D11 | Y travel ~540 mm; Y length parametric in CAD | ✅ | README §3.2 |
| D17 | Bed: adjustable panel (4 points) with a bonded steel sheet and magnets; acrylic as alternative; no glass | 🟡 | README §3.8 |
| D20 | SVG/PDF toolchain deferred; prove the machine with hand-written/scripted G-code first | ✅ | README §3.9 |
| D21 | X-carriage preload: 2 eccentric spacers on the bottom wheel pair (no slot fallback) | ✅ | README §3.4 |
| D22 | CAD migrated from OpenSCAD to PythonSCAD (ported 1:1) | ✅ | README §6 |
| D23 | 2D sketches as SVG files next to the module that extrudes them, loaded with `load_sketch()`; so far only the V-slot profiles. PythonSCAD stays the only 3D source; printed parts stay parametric in Python | 🔬 | `CODING_STANDARDS.md` §6 |
| D24 | Parametric sketches: no open interchange format carries constraints, and a Python constraint module was tried and rejected. Draw and constrain in a CAD tool and export SVG (D23) | ✅ | `cadder/docs/sketch-formats.md` |
| D25 | Y drive: motor behind the rear SK10, shaft outboard, belt 30 mm outboard of the shaft; idler and Y endstop at the **front** on both sides; printed mounts screwed to the baseboard with 4 × 25 countersunk wood screws through 9 mm bosses | ✅ | §6 |
| D26 | The Y motor and idler mounts have a **corner pocket for their SK10**, so the belt line follows the SK10 (outer face and outboard edge), not the drilling. Mounts are fitted last and screwed down with no pre-drilled positions | ✅ | README §3.2 |
| D27 | Belt clamps: flat undersides on the gantry brackets and the carriage's rear block; one cap design for all six, with the groove and tooth ridges in the cap; M3×14 | ✅ | §6 |
| D28 | **Handles and `align()`:** parts expose named handles and assemblies place hardware on them instead of repeating coordinates | 🔬 in use | `CODING_STANDARDS.md` §5 |
| D29 | **No heat-set inserts: pressed-in hex nuts everywhere**, in slots or hex shafts with a wall behind them that takes the load (`TOL.nut_wall`). **Avoid self-tapping into printed plastic**; exception: the servo's own screws in the pen holder | ✅ | README §7.1 |
| D30 | Baseboard **700 × 900 × 18 mm**; bed on 4 M5 posts adjusted from above; controller bare (no case) under the board between the runners; PSU off the board (see D38) and mains off the plywood; runners from extrusions on hand | 🟡 | README §3.8 |
| D31 | Baseboard layout: three 2040 runners on edge along X (y 150 / 450 / 750) on M5 countersunk screws into drop-in T-nuts; bed posts = M5×45 stud from below + spring + nut on the panel; steel stops 24 mm short of the panel edge; SK10s on through-bolts, the right rail's holes oversized (Ø7) for alignment; the layout is generated, not drawn | 🟡 | `python -m plotzker layout` |
| D32 | Cable management: loose round loom on printed support rails for Y, not drag chains or flat ribbon; X per D33. Revisit if the loom drags or fatigues | 🟡 | T3.8 |
| D33 | X cable: ribbon festoon in the beam's two rear T-slots, mock-up first | 🔬 | T3.8 |
| D34 | **X belt attached at the bottom of the carriage** (motor/idler axis z 70.7; the X− endstop board lies flat on its foot at the left end). Revert point: git tag `pre-x-belt-bottom` | ✅ | §6 |
| D35 | The left bracket's base extends outboard under the X idler (shelf, now carrying the D42 tower) instead of leaving it overhanging | ✅ | `BRACKET.shelf_x` |
| D36 | **CAD split into `cadder` (generic framework) and `plotzker` (the plotter)**; one repo for now, cadder moves out later. cadder never imports a project; firmware stays in plotzker. Candidates to move with cadder: `CODING_STANDARDS.md`, the generic half of README §7, the `fem-analyst` agent, generic Makefile targets | ✅ | README §5, `cadder/README.md` |
| D37 | **v1 pen holder:** pen slide in two printed sleeves on one Ø6 rod (LM6UU later), key rib against rotation, FT90M servo with a pin in a slot (the slot's clearance is the float), 90° V-block with an M5 thumbscrew. Rejected: flexure/four-bar, plastic dovetail. Alternate if the sleeves stick: 625-bearing rollers | ✅ | §6 |
| D38 | **PSU mount:** PSU on edge beside the board's right edge on two printed L brackets, fan face out, label wall up, terminal end to the front, clear of the table; printed hood with the fused, switched C14 inlet and the female XT60 (male on the controller lead); no internal partition (mains separation rests on insulation); opens only with a tool. XT60 position to recheck in T3.32 | 🟡 | README §3.6 |
| D39 | **Measure with the caliper, not from photos** (photos only for flat hole patterns) | ✅ | README §7.7 |
| D40 | **Licensing:** CC BY-SA 4.0 for the plotter's designs and documentation, LGPL-3.0-or-later for software (all of `cadder/` included); no source headers | ✅ | README §8 |
| D41 | **Controller: Creality V4.2.2 instead of the ZRIB v5.8**, which failed on the bench. Given up: spare drivers and endstop inputs (pen changer), swappable drivers. Last ZRIB state: git tag `pre-creality-board` | ✅ | `docs/controller.md` |
| D42 | **Floating belt idlers:** the idler's slider hangs on its tension screw, which runs along the belt line at the axle's height (no couple, no rail, no play); one slider for all three idlers, printed top down. Replaced the dovetail tensioners, which tilted under belt load | ✅ | `parts/floating_idler.py` |
| D43 | **Superseded hardware code is kept under `plotzker.legacy`**, outside the current machine: it may import the active code, never the reverse (a test checks it). Kept for possible reuse or a later choice of board at build time | ✅ | `src/plotzker/legacy/` |

---

## 4. Inventory (parts on hand)

Working assumption: any **commonly available** 3D-printer / maker part can be obtained.
Parts listed here are ones we specifically plan around. Dimensions are in
[`docs/hardware.md`](docs/hardware.md).

| Part | Qty | Details | Still to confirm |
|------|-----|---------|------------------|
| 2020 V-slot extrusion | several | **520 mm** long | — |
| 4020 V-slot extrusion | 2 | **520 mm** long → X beam; end bores tapped M5 | — |
| 2040 V-slot extrusion | 3 | **520 mm** long → baseboard runners | — |
| Shorter 2020 / 2040 / 4040 extrusions | a few | e.g. 340 mm 2040 | Lengths |
| V-wheels | many | Ø24 × 10 mm POM on 625 bearings; eccentric spacers | — |
| Ø10 mm hardened shafts | 2 | **700 mm** → Y axis | — |
| SK10 shaft supports | 4 | Shaft center 20 mm above the mounting surface | Bore offset from the base edges |
| SCS10UU linear bearing blocks | 4 | 2 per shaft | — |
| NEMA17 stepper motors | ≥ 3 (+1 for optional Z) | Sizes vary (39.2 mm body / 22.6 shaft, or 33.5 / 19) | Rated current (X motor label `42H-22012L-23BD`; no datasheet found) |
| GT2 belt, pulleys, idlers | assorted | 6 mm belt (plenty); common 20T pulleys and idlers | — |
| Lead screws, linear bearings, misc. bearings | assorted | No LM6UU/LM8UU found yet | Only for a stepper Z or the pen slide upgrade |
| Ø6 rod | 1 | ~200 mm; the pen holder needs 63 mm | — |
| Hobby servos | 2+ | FeeTech FT90M (pen lift) and FS90 (spare) | Horn thickness, spline height |
| **Controller: Creality V4.2.2** | 1 | [`docs/controller.md`](docs/controller.md) | Outline and holes (T3.32); factory Vref |
| Zonestar ZRIB v5.8 (set aside, D41) | 1 | Failed; don't power from 24 V | — |
| BigTreeTech TFT35-E3 | 1 | Touch screen and SD/USB G-code sender; not a motion controller | Hardware version |
| Power supply | 1 | Cheng Liang P360W24V, 24 V 15 A, 215 × 113 × 50 mm, 770 g with the inlet | — |
| C14 inlet (fused, switched), XT60H-F | 1 each | For the PSU hood | See T3.31 |
| Endstop switch boards | ≥ 3 | Creality-type, 20 × 20.3 mm | Click point, lever length |
| Wood screws | many | 4 × 25 mm countersunk (the shortest on hand) | Head diameter (*assumed* 8 mm) |
| M5 hardware for the baseboard | to buy | 12 × M5×30 countersunk + 12 drop-in T-nuts (runners); 8 × M5×35 + nuts + washers (SK10s); 4 × M5×45 + washers, nuts, springs Ø9 × 12 (bed posts) | T-nut thickness and slot lip |
| Plywood, steel sheet, magnets | to buy/cut | Baseboard, bed panel, work holding | — |

---

## 5. Key numbers (quick reference)

`python -m plotzker check` prints the current values from `params.py`.

| Item | Value |
|------|-------|
| X travel / Y travel | ~426 mm / ~545 mm (firmware limits 410 × 540) |
| Steps/mm (GT2, 20T, 1.8°, 1/16) | 80 |
| Shaft spacing | 520 mm |
| Shaft center / SCS10UU top face above the mounting surface | 20 / 33.5 mm |
| Bed top / thickest media top (above baseboard) | ~15 / ~30 mm (*design values*) |
| X beam bottom / top (above baseboard) | 58 / 98 mm |
| Carriage | Wheels 64 mm apart; front face 21.3 mm in front of the beam center; z 33.15–122.85 mm (3.35 mm over 15 mm media) |
| Tool-plate interface | 50 W × 45 H, bottom edge at z 33.15; 2 × M3 36 mm apart |
| Pen holder | Lift 7 / float 3 mm; rod Ø6 × 63; pen axis 16–22 mm in front of the carriage face; ~39 mm deep, up to z ~105 |
| Y belt | 30 mm outboard of each shaft; motor/idler axis z ~26.8; idler axle y 56.3 (±4), motor axis y 825; ~1.6 m belt per side |
| X belt | Center 26 mm behind the beam's center plane; motor/idler axis z ~70.7; ~1.2 m belt |
| Baseboard | 18 mm plywood, 700 × 900; runners at y 150 / 450 / 750, x 90–610; holes in `docs/baseboard-holes.md` |
| Bed | Panel 400 × 480 × 9 on posts at x 165 / 535, y 225 / 675; steel 352 × 432 × 0.8; post nuts up to z 22.7 |
| Pen reach (10 mm pen) | x 150–576, y 138–683 (A3 centered: x 201–499, y 240–660) |
| Y loom | Ø8, R 16; lying length 666 mm; hole (690, 150) |

---

## 6. As-built design notes

How the designed parts fit together. The principles are in README §3, the exact values in
`params.py`, and each part's hardware and print settings in its module docstring.

**Gantry end brackets** (`gantry_end_bracket.py`, left and right): a 10 mm base plate on both
SCS blocks (8 × M5), a ribbed face plate the beam end bolts to (2 × M5 into the end bores, in
a 1.5 mm locating pocket), the two Y belt clamps underneath and an M3 trigger screw for the Y
endstop, which also fine-tunes each side's home position. The beam end sits directly over the
shaft. The left bracket also carries the X idler's tower (D42) on its shelf (D35); the right
one carries the loom anchor.

**Height stack-up** (from the shaft mounting surface): shaft center 20 → SCS10UU base 7 → top
face 33.5 → beam bottom 58. The carriage's bottom V-wheels hang ~25 mm below the beam, so the
brackets lift the beam ~24.5 mm above the blocks (table in `docs/hardware.md`).

**Belts and clamps** (D27): the Y top run is cut and both ends clamp under the gantry bracket;
the X lower run is cut and clamped on top of the carriage's rear block. One cap
(`belt_clamp.py`) for all six, with the groove and tooth ridges, on M3×14 into pressed-in nuts.

**X drive:** the motor sits behind the beam at the right end (`x_motor_mount.py`). At the left
end the floating idler (`idler_slider.py`) hangs on an M3×25 screw from the bracket's tower, and
`x_endstop_mount.py` is the foot of the X− endstop board (the trigger head presses the lever
along the board). Both the motor mount and the endstop mount are clamped by two of the rear SCS
block's bolts (M5×25 instead of M5×20), so the brackets need no extra holes.

**Y drive:** per side, the motor sits behind the rear SK10 with its shaft outboard
(`y_motor_mount.py`). In front of the front SK10, `y_idler_mount.py` carries the idler tower
(floating `idler_slider`, screw head at the front) and the Y endstop's tower, in the plane of
the bracket's trigger screw. Each mount has an SK10 pocket (`sk10_pocket.py`, D26). The
right-hand parts are mirror images except the endstop tower (the board is chiral).

**X carriage** (`x_carriage.py`): an 8 mm front plate with four V-wheels (top pair on printed
8.3 mm stand-offs, bottom pair on the eccentric spacers) on M5×42 bolts; a bridge under the
beam carries the rear block with the X belt clamp and the endstop trigger. Printed front face
down.

**Work area:** X travel = 520 mm beam − carriage − end keep-outs (the tool head can't pass in
front of the SCS blocks). Y travel = 700 mm − 2 × 13.1 mm SK10 − ~125 mm gantry end − margins.

**Baseboard and bed** (D30, D31): on top, the SK10s, the Y mounts and the bed panel on four
posts; a post is an M5 stud from below with a spring in the 5 mm gap and a washer and nut on the
panel (gap 2–8 mm). The post nuts are why the steel stops short of the panel edge. Underneath,
three 2040 runners on edge (40 mm) and the controller mount (T3.32). Everything the drilling
needs is in `params.BASEBOARD`; `layout.py` makes the SVG and the hole table.

**v1 pen holder** (D37): the **body** (`pen_holder_body.py`) is a 50 × 45 mm plate with the hook
lip and 2 × M3, two arms holding the Ø6 rod, a key rib and the servo wall; printed on its left
side. The **slide** (`pen_slide.py`) has two 13 mm sleeves, the V-block (pens 7–16 mm), a yoke
with the thumbscrew and a lug with the pin slot and key groove; printed back face down. The
pen's height (~20 mm range) is set by sliding it in the clamp.

---

## 7. Ideas and future possibilities

- **Automatic pen changing:** parking slots at the edge of the work area, or a carousel.
  The tool-plate interface and connector leave room for it.
- **Extrusion "spine" tool head** (e.g. the 340 mm 2040): not for v1 (a pen needs only a few mm
  of stroke); could become its own tool head for a heavy tool needing a long Z.
- **TFT35-E3 standalone plotting** from its SD/USB (T2.6).
- **Supported rails** (e.g. SBR12) in place of the Ø10 shafts if shaft sag ever shows up.
- **FEM calibration** against a loaded printed part, to replace the assumed material values.
- **Other tool heads** (README §1 lists the non-goals for now).
