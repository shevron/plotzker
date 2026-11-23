# Project status

The state of the ongoing development: where we are, what is next, open questions,
detailed decisions, inventory, key numbers, as-built design notes and ideas. Goals,
requirements, the high-level design and the coding standards are in
[`README.md`](README.md); references like "README §3.2" point there.

> **Status:** Phase 1 (architecture) complete. Phase 3 in progress: T3.1–T3.7 and T3.9–T3.10 done (CAD
> scaffold, gantry end brackets, X carriage, X and Y motor/idler/endstop mounts, v1 pen
> holder, full assembly and the 1:1 baseboard drilling layout); STLs in `stl/`, test prints
> pending. CAD migrated from OpenSCAD to PythonSCAD
> (T3.9, D22; identical STLs). On trial: SVG 2D sketches for profiles (D23), handles and
> `align()` (D28). The CAD is split into the `cadder` framework and the `plotzker` plotter
> (T3.24, D36). Q12 answered (tap the second bore of each beam end). Q10 (SVG/PDF
> toolchain) deferred until the machine runs.
>
> **Next:** Phase 2 starts with **T2.7** (X-axis bench bring-up: print and assemble the gantry
> and carriage, wire the X motor and endstop, flash Marlin, home X; guide in
> [`docs/x-axis-bringup.md`](docs/x-axis-bringup.md)). T3.8 X cable (the ribbon festoon mock-up
> decides; the Y loom is modeled) can run in parallel; the baseboard drilling (T4.1) is unblocked.

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
- [ ] **T2.7 X-axis bench bring-up (first milestone, user's choice).** Print and assemble the
  gantry and X carriage on four SCS blocks (no Y axis, baseboard or servo), wire the X motor and
  X− endstop to the ZRIB and the 24 V PSU, flash a minimal Marlin, and check that the carriage
  moves, stops at the endstop and homes (`G28 X`). Guide: [`docs/x-axis-bringup.md`](docs/x-axis-bringup.md).
  It covers the X part of T2.1 to T2.3 and T2.5; T2.2's full configuration (dual Y, servo, SD) and
  `firmware/` follow it. `firmware/apply_config.py` applies the X-axis settings to Marlin 2.1.2.5
  (compiles with `pio run -e mega2560`; not flashed yet). *Done when:* the success criteria at the end of the guide's §5 are met,
  the user's readings (§7 of the guide) are recorded in §4 and `docs/controller.md`, and the
  endstop and direction settings found on the bench are recorded in `firmware/README.md`.

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
  Eccentric spacers measured (10 mm hex × 7.8, Ø7.1 × 2.1 boss, ~0.7 mm offset): bottom wheels
  sit 8.3 mm from the plate face; the top wheels match on printed stand-offs.
  After the first print: boss hole +0.1 (boss measured Ø7.1), the rear block's 45° flanks now run
  straight into full width (no horizontal ledge to print), 2 mm counterbores for the axle bolt
  washers/heads (M5×42 bolts). Trigger-nut and tool-plate M3 slots are flat-first (README §7.4,
  `TOL.nut_slot`); so are all other pressed-in slots (X belt clamp, gantry bracket trigger and
  loom anchor, X/Y idler tension and endstop nuts, Z-rib strap nuts).
  → `parts/x_carriage.py` 
  `assemblies/carriage.py`; STL in `stl/`. Checked: no collision with the gantry
  brackets at either end of travel, incl. a 50 × 60 mm tool-head envelope.
  - [ ] Follow-up: test-print; check wheel preload range, hook-groove fit (with the T3.6 tool
    plate) and the X belt clamp. (STL regenerated in T3.4: belt line 4 mm further back.)
- [x] **T3.4 X motor mount and X idler** at the beam ends. → `x_motor_mount.py` (right end,
  printed mirrored), `idler_slider.py` (the one slider for X and both Y idlers, T3.26) + the tower in `gantry_end_bracket.py` (left end, T3.22; `x_endstop_mount.py` is the endstop's foot),
  the X− switch lies on the idler mount's foot (D34); assembled in
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
  - [x] Fixed for the 4 × 25 mm countersunk wood screws on hand: both mounts' feet have 13 mm
    bosses 9 mm thick (`params.WOOD_SCREW`, `parts/wood_screw.py`) with a 90° countersink, so
    the screws stop 2 mm short of the baseboard's underside; the feet stay 6 mm thick.
  - [ ] Follow-up: test-print; check the pocket corner against an SK10 and the
    belt tension range, and the trip point (adjust with the
    trigger screw length); measure where the switch clicks (modeled at 75 % of the lever's
    travel) and check the board's assumed body offset (2.5 mm right of center) and lever
    length (13.5 mm); check that a plug fits on the connectors; check the idler plate against
    the wood-screw positions; measure the SK10 bore offset from the base edges (it limits
    belt parallelism).
- [x] **T3.6 v1 pen holder (tool head).** Gravity-loaded pen slide on a Ø6 rod in two
  printed sleeves, lifted by an FT90M servo (D37); V-block + M5 thumbscrew clamp for 7–16 mm
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
    of travel (done in T3.7: clear at all four corners).
- [x] **T3.7 Full assembly and baseboard layout.** Assembly model for fit checks (travel,
  clearances, 15 mm media under the head). 1:1 baseboard drilling layout: SK10 positions,
  motor mounts, bed-panel adjustment points, runners, electronics.
  - [x] ZRIB mount (D30): `parts/zrib_hanger.py` ×2 and `parts/zrib_guard.py` ×2, `hardware/zrib.py`,
    `assemblies/zrib_mount.py`; the mount hangs 39 mm below the baseboard (a 2040 runner on edge is
    40). Checked: the board threads between the legs from below, no collisions, everything
    connected; the PCB thickness (1.6) and the tall-part layout are *assumed*.
  - [x] Layout (D31, `params.BASEBOARD`): three 520 mm 2040 runners on edge along X, 300 mm apart
    (y 150 / 450 / 750), 4 M5 countersunk screws each into drop-in T-nuts; four bed posts (M5×45
    studs from below, spring, nut on top of the panel) 15 mm in from the panel corners; the ZRIB
    mount between runners 1 and 2, toward the right (x 520, y 300, USB side facing +y); SK10s on
    M5×35 bolts with nut and washer underneath, oversized Ø7 holes under the right rail so the
    gantry can align it (README §3.2). The Y mounts are *not* pre-drilled (D26).
  - [x] `layout.py` + `python -m plotzker layout` → `docs/baseboard-layout.svg` (1:1, print at
    100 %) and `docs/baseboard-holes.md` (28 holes, coordinates from the front-left corner), both
    generated from `params.py`.
  - [x] `assemblies/baseboard.py` (drilled board, runners and screws, SK10 bolts, bed and posts,
    ZRIB) and `assemblies/machine.py` (everything, pen holder included; `renders/machine.png`).
    Design checks added: runners and posts on the board and clear of each other and of the ZRIB
    mount, nuts clear of the steel and the carriage, and the **pen reaches all of a centered A3
    sheet** (pen x 150–576, y 138–683 vs A3 x 201–499, y 240–660). Tests: the machine is connected;
    the pen holder, up and down, clears everything at the four travel corners; fasteners sit in
    their holes; no part of the ZRIB mount touches a runner.
  - [ ] Follow-up (test print and build): the ZRIB mount (nut slots, wood screws, 5 mm post height
    against the board's pin tails); check the bed panel's sag between the four posts (est. 0.2–0.4
    mm; add a fifth post at the center if it shows) and the T-nut thickness and lip (*assumed* 4 /
    1.8); the pilot holes (Ø2.5) in your plywood; the USB cable reaches the board's rear edge
    between runners 1 and 2 (95 mm gap, entering from the side), else move the mount.
- [ ] **T3.8 Cable management** (D32: loose loom on printed support rails). Moving cables: X
  motor, X endstop (gantry, move in Y) and the pen servo (carriage, move in X and Y); the Y motors
  and Y endstops are static.
  - [ ] **Loom spec (user builds it to this; the CAD is designed against it, values *assumed*
    until the real loom exists).** Conductors on the gantry loom: X motor 4 (24 AWG or thicker:
    ~1.5 A), X endstop 3 (signal, GND, 5 V), pen servo 3 (signal, GND, 5 V) = 10; servo and endstop
    wires may be 26–28 AWG. Outer diameter of the finished bundle in its sleeve **≤ 8 mm**, flexible
    (silicone or fine-stranded wire; no stiff solid-core), bend radius **≤ 16 mm** (2 × diameter).
    Round loom is enough: a flat ribbon would save width but 28 AWG ribbon is marginal for the
    motor current and needs a connector board, so it is not worth it unless the bundle can't get
    under 8 mm. Length: from the ZRIB to the gantry anchor about **1.1 m** (half the Y travel
    ~270 mm for the fold, the run along the board to the ZRIB, and slack); cut at build. The X
    part: carriage to beam end about **0.5 m** of the servo and endstop wires only (the motor wires
    leave at the beam end), with 15 cm spare. Connectors: keep each device's plug on the device end
    (servo, endstop, motor) and use one small inline connector or terminal block at the gantry
    anchor, so the gantry can be taken off.
  - [x] Y loom (`params.LOOM`, `parts/loom_anchor.py` ×1, `parts/loom_rail.py` ×6,
    `assemblies/loom.py`): the anchor block sits on the right bracket's base outboard of the X motor
    mount (2 × M3×16 into nuts pressed in from the outboard edge; groove along x, zip tie through two
    slots and a channel under the block; relief for the loom's first bend). The loom leaves
    outboard, drops 40 mm to the baseboard at x = shaft + 48, runs back along the board, folds in a
    U (R 16, legs 32 apart) and returns along x = shaft + 80 to a Ø12 hole at (690, 150) in the
    baseboard, then under the board to the ZRIB. The fold travels half as far as the gantry; with
    the gantry at the back it just clears the drop (apex y 781, 5 mm short of the Y motor mount).
    Lying loom length 666 mm. Six rail segments (80 mm, every 100 mm from y 200) keep the loom off
    the belt: wall face 42 mm from the shaft, foot toward the belt, 2 wood screws each, not
    pre-drilled (laid out by tape). No outer rail: the strip beside the belt is too narrow for
    one. Design checks and tests (loom clears everything at front, middle and back).
  - [ ] **X cable: options discussed (kept here so we can revert).** Moving cables: the servo and
    X-endstop wires (6 thin conductors) between the carriage and the right beam end; the X motor is
    fixed at the right end. Travel 426 mm; the carriage needs ~200 mm of slack as it moves.
    | Option | Verdict |
    |--------|---------|
    | Sleeve hanging behind the beam | Rejected: droops onto the bed |
    | U fold on the beam top | Rejected: the carriage bridge rides there; 20 mm is too narrow |
    | Drag chain (7×7, bend R ~18, 45–60 mm fold, may overhang a beam end) | Not pursued: the fold can sit past the beam end, but the chain then needs a ~520 mm tray at z ≥ 118 (above the X motor body, z ≤ 115, and the endstop/trigger at the left end) and a carriage mount; the tray cannot hang from the beam top (carriage bridge) or rear (X belt loop 13 mm behind the face), so it would hang from both gantry brackets: heavy |
    | Flat silicone ribbon in the 10 mm gap between the beam's rear face and the belt, shallow vertical loop at the carriage | Fallback: lightest; ribbon fatigue under repeated flex |
    | Cut X travel to ~350 mm to free room | Fallback: README R3 only needs ≥ 320; doesn't remove the support problem for a chain |
    | Take-up (floating) pulley, elastic cord | Analyzed, **not recommended** (see below) |
    | Ribbon festoon in the beam's two rear T-slots | **Candidate to try**: see below |
  - [ ] **Take-up pulley: analysis.** Layout that fits: both legs at z ≈ 121, y 36 / 46 behind
    the carriage's rear block (above the X motor, z ≤ 115, and the left endstop board, z ≤ 117.4),
    fixed clamp on an L-post from the beam's lower rear T-slot (z 68, behind the belt) at x ≈ 580,
    leg 2 clamped to the carriage's rear block. Blockers: (1) the pulley moves half the carriage
    travel = 213 mm, and an elastic cord stretched over 213 mm changes its force 3× or more (a
    weight over a pulley would be constant but needs 106+ mm of free vertical room beside the
    left bracket, where the Y belt clamps are); (2) the left anchor must be left of the pulley,
    i.e. a new tower on the X idler mount (its top is at z 105, the endstop board at 117);
    (3) a rod for the pulley to ride on, or the pulley swings. Cable sag is not a problem (0.5 N
    tension gives ~2 mm over 480 mm).
  - [ ] **Ribbon festoon in the beam's rear T-slots (chosen to try, D33; mock-up first).** The 4020's
    rear face has two T-slots, 20 mm apart (z 68 and 88). A thin flat ribbon lies in the lower
    slot (fixed run), makes a free U (R ~ 10) outside the face and returns in the upper slot (moving
    run); the slots guide both runs and the U moves along the beam at half the carriage speed. No
    tray, no tension element. The fixed end is at the right (x ≈ 595, ribbon leaves the slot mouth
    there and joins the Y loom at the bracket); the moving end leaves the upper slot next to the
    carriage through a small printed shoe on the rear block and clamps there. Numbers: ribbon about
    0.55 m in the slots (lower run 478 → 265 mm, upper run 20 → 233 mm as the carriage goes left to
    right) plus the lead to the Y loom. **The carriage pushes the upper run toward the fold when
    it moves left**, so the ribbon must be stiff enough to push through its slot.
  - [ ] **Mock-up (user, before any CAD).** Ribbon spec: flat, silicone-insulated, 6 conductors
    (28–30 AWG; 3 servo, 3 endstop), **thickness ≤ 1.2 mm, width ≤ 7.5 mm** (it stands on edge in the
    slot cavity: 12 mm wide, 6.1 deep behind a 1.85 mm lip, 6.2 mm neck), about 0.7 m. Test on a
    spare 520 mm 2040 or 4020 offcut with the slots as the rear face: (1) lay 0.3 m in one slot and
    form the U into the other; (2) push and pull the free end by hand over ~200 mm at the speeds
    of a plot (≈ 100 mm/s) and watch whether the ribbon buckles out of the slot, drags, or
    snags at the neck; (3) 1000 back-and-forth cycles; check the insulation for wear and continuity.
    Report: pass / buckles / drags, and the ribbon's width, thickness and bend radius. If it
    fails, the fallbacks are a short drag chain with a tray, or cutting X travel (table above).
  - [ ] Follow-up: test-print the anchor and one rail; check the zip tie path, the nut slots (M3 from
    the outboard edge), that the loom seats in the groove without the bend flattening it, and the
    real loom diameter and bend radius against the *assumed* 8 / 16 mm.
- [x] **T3.10 Roll out handles (D28).** Handles are on the X carriage (wheel axles, belt clamps,
  trigger screw), the Y motor and idler mounts (motor, pulley, motor screws, axle, tension screw,
  endstop board frame), the X motor and idler mounts and the X endstop mount (motor, pulley, axle,
  board frame), the pen holder body and slide (rod, servo, horn, clamp screws, thumbscrew and its
  nut) and the ZRIB hanger (board, screws, nuts, strap); the assemblies place hardware with
  `.align()` instead of repeating coordinates. The chiral Y endstop board keeps its own frame
  (`geometry.frame_handle` / `frame_axes`, allowed to be left-handed) and flips its u axis on the
  right side. Geometry unchanged: before and after, every assembly item and every part has the
  same volume and bounding box (one 0.1 mm rounding flip in the servo). Left as hand-derived on
  purpose: hardware stacks along an axle (washers, idler, nut offsets), which are hardware
  dimensions, and the pen holder's pin (its horn hole depends on the lift angle).

**Fixes after the first test print of the belt-at-bottom design (D34).** Tackle one at a time;
the printed carriage, motor mount and idler mount are the test pieces.

- [x] **T3.11 X motor mount: M5 heads collide with the M3 motor bolts.** The heads of the M5
  bolts that clamp the mount to the bracket hit the heads of the two bottom M3 motor bolts, so
  both cannot be fitted. Preferred fix: counterbore the M5 heads ~2 mm into the foot (check the
  foot is thick enough). Fallback: raise the motor, and with it the pulley axis, idler and belt,
  by 1–2 mm (re-check D34's 1 mm motor clearance and the carriage). Rejected: fixing the motor
  with only its two top M3 screws.
  Done: 2 mm counterbores (`XDrive.foot_head_recess`) for the two M5×25 heads in the foot (3 mm
  left under them; thread engagement in the SCS block is now 12 mm = its full thread depth).
  The M3×10 motor screws are now modelled (handle `motor_screws`) and a test checks they clear
  the M5 heads (10.9 mm³ overlap before, none now). Reprint the motor mount.
- [x] **T3.12 Side-inserted M3 nut pockets are too loose.** The pockets for nuts slid in
  sideways (perpendicular to the bolt axis) let the nut play and spin as the bolt is tightened,
  worst in deep pockets where the nut can't be held by hand. Suspect: the flat-first rule (§7.4)
  and/or the pocket thickness (`TOL.nut_slot`). Measure the printed pockets against the nuts,
  retune the clearances, and revisit the flat-first rule for side-inserted slots (it targets
  pressed-in vertical pockets; the user suggests it may need reverting here).
  Done (user's choice: hex-profile pocket): new `nut_slot.nut_slot()` (floor and lower walls follow
  the hex, straight walls to the entrance, no supports) replaces the rectangular slots at the
  gantry bracket (loom ×2, trigger), Y and X idler tension nuts, ZRIB hanger strap nuts and the
  carriage (tool plate ×2, trigger). Measured M3 nut: 5.4 AF × 2.25 (model was 5.5 × 2.4).
  Measured printed slot (PETG) 6.6 wide × 2.8 thick for a design of 6.70 × 2.7, i.e. ~0.1
  narrower across and ~0.1 thicker: `TOL.nut_slot` = 0.3 (AF oversize), `TOL.nut_t` = 0.1.
  Expected printed pocket: 5.6 AF (0.1 per side) × 2.45 thick. The two-nut clamp slots keep a
  rectangular slot until T3.13. Reprint to check (a small test piece with slots would do).
- [x] **T3.13 Belt clamp nuts: two nuts in one pocket.** Inserting two nuts one after the
  other into one pocket is very hard (the second is hard to seat). Find another solution: a
  pocket exactly two nuts long so both can be pushed flat against each other, or a different
  clamp fastening (one nut per screw, a longer screw into one nut, separate pockets, or a
  clamp plate with its own threads). Propose options with a trade-off table (§7.1) before
  changing anything.
  Done (user's choice: separate side slots): each of the 4 carriage clamp nuts has its own
  hex-profile pocket (`nut_slot`): the rear nut from the back face (~5 mm push), the front nut
  from the nearer end of the block (~10 mm push), flat-first, with the 4 mm roof above kept so
  the belt bearing face is intact; no clash with the trigger screw (z 52.7 vs the nuts at 57.6).
  The Y clamps in the gantry brackets use axial hex shafts from the top and are unchanged. Reprint
  the carriage.
- [ ] **T3.14 X endstop: bolt and switch not aligned in Z.** The trigger bolt head hits ~2 mm
  too low and barely brushes the lever's underside. Main suspect: solder joints protrude up to
  ~1.8 mm from the underside of the endstop board, so it can't sit flat on the idler mount's
  foot. Accommodate the protrusions (relief pockets or a recess under the board, or a spacer),
  and re-measure the board and lever (`hardware/`, `docs/hardware.md`); ask the user for
  measurements and photos. Check whether the Y endstops have the same problem.

  Measured (user): flat PCB underside 1.8 mm above the table (solder up to 1.8 mm, uneven, tallest
  at the NC leg, front-left); lever 4.2–8.0 above the lowest solder tip = 2.4–6.2 above the flat
  underside, which matches the model (`lever_z` 4.15). So the board was sitting ~1.8 mm too high
  on its solder. Done: the idler foot is recessed 2.2 mm under the board (`XEndstopMount.relief_depth`)
  except for Ø6 lands round the two screw holes, with a test using a 1.8 mm solder slab. That
  explains ~1.8 mm of the ~2 mm miss, but not why the head only "brushes" the lever (the model
  says a Ø5.3 head centered on the axis still overlaps the raised lever by ~2.6 mm): after the
  reprint, if it still misses, measure the printed trigger screw axis height above the foot top
  (design 4.15 mm above the board seat) and the foot thickness (5 mm). The Y endstops are
  also affected (the board stands on the tower with its solder side against it, so it sat up to
  1.8 mm off the tower along x, off the trigger axis): fixed the same way, a 2.2 mm recess in the Y idler
  mounts' tower face except for Ø6 lands round the screw holes (`YEndstopMount.relief_depth`), both
  sides tested. Reprint both Y idler mounts.
  Second contributing factor (user): the trigger screw's hole was a loose fit and the screw (M3×16)
  long, so tightening it into the captive nut pulled the shank down and the head rose. Done:
  screw shortened to **M3×12** (`CARRIAGE.trig_screw_len`, still ~5 mm through the nut at the
  end of adjustment) and the hole is now a snug Ø3.2 (`TOL.slide_d(3)`, was 3.4). Reprint the carriage.

- [x] **T3.15 Generic tensioning idler (prototype).** The X idler's cantilevered axle tilted
  under belt tension and the belt felt bumpy. Replacement: the axle is held at both ends by a
  U-shaped slider (two 6.8 mm arms, rear wall, plate) riding on a dovetail rail, two separate
  prints (0.2 mm per side); an M3 screw through the rail's end block pulls the slider away from
  the belt into a captive nut in its rear wall; the idler has 1 mm end play on each side so it
  self-aligns with the belt. → (the prototype's code and STLs were removed in T3.25; the floating idlers of T3.22–T3.23
  replaced it.)
  - [ ] Follow-up: test-print (slide fit and `slide_gap`, M5×25 axle + nut, M3×25 screw; the
    slider prints lying on its back, no bridges; its M3 nut slot is 0.2 mm thicker than the usual
    nut trap, `nut_slot_extra`, because the long slot came out too tight).
- [x] **T3.16 Tensioner on the left gantry mount (X idler).** The generic tensioner applied to
  the X idler, with the rail merged into `x_idler_mount.py` (one part, no extra screws; the old
  cantilevered plate, slot, tension-nut slot and `x_idler_spacer` are gone) and the slider as
  `x_idler_slider.py` (`params.X_TENSIONER` = the generic one on the foot, travel 8 mm).
  Changes needed on the way: the foot grows forward (to y 16) and ~5 mm outboard under the
  rail (the end block's outer face is at x −47; the bracket ends at −38, so 9 mm overhang); the **axle bolt head
  is on the rear arm** (`head_side`: the front arm is 3 mm from the bracket's beam face); the
  slider's **plate and the ridge stop short of the endstop plug's keep-out** (x −22.2), so the
  plate is 10 mm long instead of 23 and only the arms reach on over the idler (`plate_cut`),
  their undersides chamfered at 45° (no print overhang; the chamfer keeps a wall round the nut
  pocket on the front arm and the bolt hole on the rear arm, and the rear arm stays above the
  plug space); the tension screw is M3×20, tip clear of the keep-out when tight.
  Idler moved 3 mm toward the motor (x −21 at mid-travel, same belt line; was −24), end block 5
  mm thick, 0.5 mm stop gap, to cut the overhang from 13 to 9 mm; the screw head stays
  reachable from outboard. Test: slider free over its
  whole travel, the plug keep-out stays free.
  - [ ] Follow-up: test-print; check that the short dovetail (10 mm) doesn't rock under belt
    tension, and the foot's 9 mm overhang past the bracket (the end block is loaded in x).

- [x] **T3.17 Tensioner on the Y idler mounts.** The same dovetail tensioner as the X idler (T3.16)
  on both Y idler mounts: rail and screw block built into the foot (`parts/y_idler_mount.py`),
  slider as `parts/y_idler_slider.py` (left + right, mirror images; `params.Y_TENSIONER`, travel 8
  mm). The slide runs along y (belt direction), the screw block is at the **front** (screw head
  reachable from the front, tensioning no longer needs the gantry moved back), the axle bolt
  head is on the inboard arm. The idler position is unchanged (y 56.1 at mid-travel, clear of
  the endstop plug keep-out). Changes: the old outboard plate, axle slot and tension-nut slot
  are gone; the foot is one plate from the block to the endstop tower (x −60 to −20, y 29 to 108),
  wood screws at its outboard strip; the tower is 10 mm thick (`tower_t`, was 10.35 with the old
  plate); the dovetail is 3 mm high with a 7.5 mm roof so the slider's plate stays under the low
  idler (1 mm clear of its flange). Test: slider free over its whole travel on both sides. The
  baseboard drilling layout is regenerated (the foot footprint changed; the mounts are still not
  pre-drilled).
  - [ ] Follow-up: test-print; check the belt tension range, the plate clearance under the idler
    and the dovetail fit.

- [ ] **T3.18 FEM check sub-agent.** An independent `fem-analyst` sub-agent checks new or
  significantly changed parts against their planned loads and allowed deflections (PASS/FAIL
  plus optional pictures of the failure). Parts become Python classes holding all their
  properties (print profile, material, build direction, loads, criteria); a CLI prints them for
  the sub-agent. Plan, decisions and open points: [`docs/fem-subagent-plan.md`](docs/fem-subagent-plan.md).
  Subtasks (F0–F5 in the plan): **F0 toolchain spike ✅** (gmsh + CalculiX from FreeCAD: benchmark
  within 1 %, X idler slider and mount mesh and solve in ~2 s, offscreen pictures work; the gantry
  end bracket also meshes once the STL is cleaned and its holes exported coarser, no CAD change
  needed; results in plan §11); **F1 part class, print profiles and materials TOML, first three parts (X idler
  slider, X idler mount, gantry end bracket) ✅** (`python -m plotzker part NAME --json`; assumed
  loads and limits listed in plan §12 await the user's review); **F2 runner and verdicts ✅** (`python -m plotzker fem NAMES`; cantilever benchmark within 1.2 %; first verdicts in `fem/verdicts.toml`, plan §13; speed and stability round in §14: mesh-independent regions, one mesh unless near a limit, scaled proportional cases, threads, graded mesh); **F3 visualization ✅** (`--viz`: utilization, displacement and hot-spot pictures plus a `.vtu` per load case, plan §15); **F4 agent definition and process edits ✅** (`.claude/agents/fem-analyst.md`, `docs/fem.md`, README §7.8, CLAUDE.md; dry run accepted, plan §16); F5 later (two slices done, plan §17 and §19: `fem-status`, bearing load, all structural parts defined and checked; plan §20: beam seat as a support, friction zones on the mount feet; still open: remaining parts, assemblies,
  calibration). *Done when:* a dry run on a real part gives a report the user accepts.

- [x] **T3.19 Shelf under the X idler mount.** FEM (plan §21) showed that the X idler mount's foot
  and end block hang 4-9 mm past the left bracket's outboard edge with nothing under them, and the
  screw head's pull bends that overhang (utilization 9.2). The left bracket's base now reaches out
  to `BRACKET.shelf_x` (−48, 10 mm) over the mount's footprint (`BRACKET.shelf_y`, y 16…62.5), same
  thickness, flat underside (left bracket only; the right bracket's motor mount sits fully on its
  base). Clearances checked against the whole machine at the front, middle and back of the gantry's
  travel: no overlap; nearest part the Y belt, about 5 mm; X and Y endstop keep-outs clear. Design
  check added ("Bracket shelf doesn't reach the X idler mount's outboard end"); the bracket grows to
  68 × 125 mm (+4.7 cm³). *Done when:* checks and tests pass, STL and renders regenerated, FEM
  re-run (plan §22): the mount's worst value halves (9.3 to 4.3) and the left bracket passes (plan §23).
  - [ ] Follow-up: test-print the bracket (print bed fit; the shelf's underside is flat, no supports).

- [ ] **T3.21 Tensioner tilt under belt load (found on a printed X idler).** The belt pulls the
  idler axle 14.5 mm above the tension screw, so a couple twisted the slider in its dovetail; the
  X slider's plate was only 10.4 mm long (shortened for the endstop plug), so the 0.2 mm clearance
  allowed a 2.7° rigid tilt. The part checks could not see it (rigid dovetail, no stiffness for
  play, deflections never added). **Done:** the `Assembly` check (plan §24, `docs/fem.md`): it
  failed the X tensioner (vertical 0.55 mm vs 0.2, along belt 1.25 vs 0.6) and the Y tensioners
  (vertical 0.24-0.32 vs 0.2). **X fixed by T3.22, Y by T3.23 (below).**
- [ ] **T3.22 Floating X idler on a tower in the left bracket.** A screw at the axle's height,
  along the belt line, holds a rail-less slider: no couple, no dovetail, no play. The M3 screw's
  head is on the tower's outer face (hex key from outside, M3 DIN 9021 washer under it); a
  captive nut at the rear of the slider's wall pulls it toward the tower, and a blind tunnel in
  the wall takes the screw's tip as it moves (so the wall is 17 mm thick). The tower (12 mm plate,
  two 8 mm side walls to x = −23) is part of the left bracket (`gantry_end_bracket.py`, shelf under
  it from `BRACKET.shelf_x`); the walls are gussets and loose guides (they stop the slider rolling
  while the screw is turned). The idler mount is gone: its foot is now `x_endstop_mount.py` (not
  structural: foot under the endstop board, clamped by the rear bolts). The slider prints on its
  side (layers along the arms that carry the pull). New params `X_IDLER` (`params.XIdler`),
  replacing `X_TENSIONER`. **FEM (belt preload / peak):** slider MARGINAL (strength 0.46 / 0.41,
  axle moves 0.04 mm); bracket FAIL by its own 0.1 mm vertical budget at peak (tower seat
  0.09 / 0.16 mm; strength 0.69 / 0.62); X assembly check **MARGINAL** (vertical 0.11 / 0.19 mm
  of 0.2; was FAIL at 0.55 / 0.76). The tower reaches 20 mm further out than the old block
  (outer face x = −68 vs −48). **Open:** print and test (ring-and-wall fit, 0.5 mm wall gap; the
  round 3.4 mm hole in the plate prints lying on its side; the slider prints upside down, top on the bed, so its layers are parallel to the belt's pull and the nut tightening; its arm ends are 9 mm round with a 45° top front corner so that nothing droops or flips it in a slicer, plan §27); decide the Y tensioners' fix.
  - [ ] Follow-up: X idler position (`X_DRIVE.idler_x`, now −21): moving it inboard shortens the
    overhang by the same amount, at the cost of X travel (16 mm spare).

- [x] **T3.23 Floating Y idlers.** The same floating idler as the X one (T3.22) on both Y idler
  mounts: no rail, the M3 screw along the belt line at the axle's height through a tower at the
  front of the mount's foot (plate 11.4 mm, two 8 mm walls, `Y_IDLER`); the slider is the same
  part as the X one (`parts/floating_idler.py` builds both: `params.FloatingIdler`, `X_IDLER`,
  `Y_IDLER`), head on the inboard arm, printed upside down (top on the bed). The tower's walls stand on a pad on
  the foot, the foot's wood screws moved outboard of the walls (bosses beyond the outboard wall),
  and the foot reaches 19 mm further to the front (tower's outer face at machine y 14). The
  dovetail (`Y_TENSIONER`) is gone from the machine, and so is the generic prototype. Both screws are M3×25 with a large M3 washer (the X tower plate was cut from 12 to
  11.4 mm for it; the M3×30 it needed before made the slider's wall 4 mm thicker). **FEM:** mount
  PASS (strength 0.45 / 0.40; tower seat 0.06 / 0.01 / 0.02 mm), slider MARGINAL (0.50 / 0.44),
  Y assemblies PASS; X (11.4 mm plate): bracket tower seat vertical 0.082 / 0.147 mm (peak over its
  own 0.1), X assembly MARGINAL. **Open:** print and test both ends.

- [x] **T3.20 Design diff tool.** `python -m plotzker diff [REV_A [REV_B]]` (`make diff`)
  compares the printable parts of two git revisions or the working tree (default `HEAD` →
  working tree) and, in the end, shows the changes visually in a static HTML report. Phases:
  **1 snapshot + part comparison ✅** (each revision built in a temporary `git worktree`,
  cached by commit in `build/diff/`; parts added/removed/changed with volume, size and origin
  deltas; `--json`, `--all`; now `cadder/src/cadder/diff/`, `cadder/tests/test_diff.py`); **2 HTML report ✅** (one self-contained
  `index.html`, plain WebGL2 viewer with no libraries: ghost overlay, swipe, before/after, views, opacity; `diff/report.py`, `diff/viewer/viewer.html`; `--open`, `--no-html`); **3 added/removed material ✅** (manifold3d booleans `B−A` green / `A−B` red, slivers < 0.01 mm³
  dropped; section plane with cap colour; zoom to change; `diff/boolean.py`; swipe was in phase 2); **4 assembly diff ✅** (instances matched by geometry, so it works on old revisions without
  names: unchanged, moved, modified, added, removed; labelled by the printable part of the same
  volume; `diff/assembly.py`; viewer lists them and isolates one; sub-assembly roll-up and named
  instances remain open: assemblies are flat lists of solids today); **5 polish ✅** (per-part source diff, `params.py` diff,
  commit and changed-file list, FEM verdict hints from `fem/verdicts.toml`, thumbnails, `--serve`;
  `diff/source.py`). *Done when:* a change to a part and to an
  assembly can be seen in the browser as an overlay with the change highlighted.

- [x] **T3.24 Split the CAD into a framework (cadder) and the plotter (plotzker).** The package
  `plotter_cad` is renamed `plotzker` (like the repo), and everything that isn't the plotter moves
  to **cadder** (D36), a uv workspace member in `cadder/` that will later get its own repo:
  part classes (`Part` → `MaterialPart` → `PrintedPart`), `Assembly` / `AssemblyCheck`,
  handles, geometry helpers, regions, print tolerances and nut slots, the material library
  loader, the vendor-hardware catalog, 1:1 SVG drawings, FEM, the design diff, renders, the
  FreeCAD assembly export/build, and the command line. A project is a `cadder.project.Project`
  (`plotzker.project.PROJECT`, found through `[tool.cadder]`); `python -m plotzker` and
  `cadder` are the same CLI. The plotter keeps its params, `TOL` values, parts, assemblies,
  assembly checks, loads, materials data, baseboard layout, FreeCAD assembly definition, the
  endstop/ZRIB boards and the firmware. One part registry (`PARTS`): the 7 parts without FEM data
  are plain `Part`s. cadder never imports plotzker (ruff TID251, a test); its tests use a fixture
  project (`cadder/tests/fixture`). Revert point: git tag `pre-cadder-split`. Verified: STLs,
  part specs and FEM verdicts unchanged; the FreeCAD file has the same components, placements,
  joints and GUI state; the drilling layout output is identical; the design diff builds
  revisions from before the split. **Open:** where cadder's docs and agent live (see D36).
- [x] **T3.25 Nut pocket tolerances and orphaned prototype parts.** Measured on prints: the X
  slider's nut pocket came out 2.63 mm thick for a 2.35 mm nut (the nut fell out), so
  `nut_slot_extra` is 0.2 → 0 (designed 2.5 mm, expected about 2.43 printed); side-inserted slots
  (endstop board, belt clip) were tight, so `TOL.nut_slot` is 0.3 → 0.4 (0.05 mm more per side).
  Reprint to check both. Removed the superseded generic tensioner prototype: `parts/tension_idler.py`,
  `assemblies/tension_idler.py`, `TensionIdler` / `TENSION_IDLER`, the dovetail play term, their
  design checks and tests, the STLs and renders `tension_idler_rail`, `tension_idler_slider`,
  `tension_idler_fit`.

- [x] **T3.26 One slider for all three idlers.** The X slider and the Y sliders were the same
  shape (checked on the STLs): `X_IDLER` and `Y_IDLER` differ only in position, and the Y left
  slider was just the mirror image (head on the other arm). Now one part, `idler_slider` (print
  ×3, `parts/idler_slider.py`), with the axle bolt's head on the same arm everywhere
  (`head_side` +1). On the Y side the left mount's tower has its head pocket on one wall and
  the right mount's on the other (`y_idler_mount.idler_for`), so the unmirrored slider fits both;
  the head is inboard on one Y side and outboard on the other. FEM: one slider check (X frame,
  same belt loads), mounts and assemblies re-run. Replaces `x_idler_slider`,
  `y_idler_slider_left/right`.

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
| Q13 | Under-board space for the ZRIB | ✅ Board 95 × 110 mm, 22 mm from its bottom to the heat sink tops, 4 × Ø3 holes 100 × 80 mm; mounted under the baseboard with its components down (D30, `parts/zrib_hanger.py`) |

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
| D22 | Migrate the CAD from OpenSCAD to PythonSCAD: a `plotzker` Python package (`src/`), pip `pythonscad` module for STL export, PythonSCAD app for renders/preview. Ported 1:1 (all 8 STLs geometrically identical); the old `.scad` files were removed afterwards. D2 originally named OpenSCAD | ✅ | README §6, T3.9 |
| D23 | **Experiment:** 2D sketches as SVG files next to the module that extrudes them (sketch → extrude workflow), loaded with `geometry.load_sketch()`. First use: the V-slot 2020/2040 profiles (`hardware/vslot_2020.svg`, `vslot_2040.svg`). PythonSCAD stays the only 3D source; printable parts stay fully parametric in Python for now | 🔬 Trial | README §6 |
| D24 | Parametric sketch formats researched (`cadder/docs/sketch-formats.md`): no open interchange format carries sketch constraints. A Python constraint-sketch module (python-solvespace) was tried on the 2020 profile and **rejected**: it doesn't allow GUI drawing and adds little over plain PythonSCAD. **Stay with SVG (D23)**: designers draw and constrain in their CAD tool (e.g. FreeCAD) and export SVG. Revisit: automate the export with FreeCAD as a dependency | ✅ | `cadder/docs/sketch-formats.md` |
| D25 | Y drive layout: motor **behind the rear SK10**, shaft outboard, belt 30 mm outboard of the shaft; idler with slot tensioner in front of the front SK10; Y endstops at the **front** on both sides, on a tower of the idler mount; printed mounts screwed to the baseboard with 4 × 25 countersunk wood screws through 9 mm bosses. Costs ~25 mm of baseboard length at the back; belt ~1.5 m per side | ✅ | T3.5, §6 |
| D26 | The Y motor and idler mounts have a **corner pocket for their SK10** (cut-out in a 6 mm foot: a 24 mm end-wall finger against the shaft-end face and an outboard side wall; open toward the inboard side and the other SK10; the finger is kept short so it stays sturdy), so the belt line is referenced to the SK10's outer face and outboard edge instead of the baseboard layout and SK10 width/chamfer tolerances don't matter. Mounts are fitted last, around the already aligned SK10s, pushed into the corner, and screwed down through plain holes (no pre-drilled positions). The SK10's own bore tolerance limits the result | ✅ | README §3.2, T3.5 |
| D27 | Belt clamps: flat undersides on the gantry brackets and the X carriage's rear block (no belt channel: no bridges or overhangs); one cap design for all six clamps, with the groove (between two rails) and the tooth ridges in the cap. Belt lines drop 1.08 mm (derived); screws M3×12 | ✅ | T3.2, T3.3, §6 |
| D28 | **Handles and `align()` for assemblies (trial).** Parts that hardware or other parts attach to expose named handles (4×4 matrices set with `geometry.set_handles`, read with `get_handle(s)`); assemblies place the hardware with `.align(handle)` instead of re-deriving hole coordinates, and the part's own cut-outs use the same handle constants, so a hole and its screw can't drift apart. Rolled out to the carriage, the X and Y mounts, the pen holder and the ZRIB hanger in T3.10 (chiral boards use `frame_handle`). `fillet` and `MultiToolExporter` evaluated and not adopted yet | ✅ trial | README §7.4, T3.10 |
| D29 | **No heat-set inserts: pressed-in hex nuts (nut traps) everywhere.** The nut sits in a slot or hex shaft with a wall behind it that takes the load (`TOL.nut_wall`, 2 mm). Y/X idler tension screws: slot from the top; X endstop pad screws: slots from the rear face; belt clamp screws (brackets): hex shafts from the top, nut 4 mm above the underside (`CLAMP.nut_z`), M3×14; X carriage rear block: slot from the back; tool-plate screws: slots from the bottom edge. Endstop boards (X and Y): M3 through the board and the mount into a nut in a hex pocket on the pad's underside (X, M3×6) or the tower's outboard face (Y, M3×12), not self-tapping into printed pilots; **avoid self-tapping into printed plastic wherever possible** (it wears and is a failure point). Exception: the servo's own screws in the pen holder. Dropped the `Preload.SLOT` carriage fallback (eccentric spacers are available) | ✅ | README §7 rule 2 |
| D30 | **Baseboard and bed (T3.7), first decisions:** baseboard **700 × 900 × 18 mm** (the Y drive reaches x 4.5–645.5 and y 18–821 on the old 650 × 850); bed panel on **4 × M5 screw + nut posts** (adjust from above); the **ZRIB goes under the baseboard between the runners**, the **PSU stands off the board on its own base** (its fan inlet is on the bottom face and needs ≥ 25 mm of free air; under the board that would need an 80 mm drop; also keeps mains off the plywood); runners from the extrusions on hand, 2040 on edge with low feet. The **ZRIB is mounted bare** on two printed hangers with a minimal guard strap each (no case: exposed electronics, free airflow; the strap is optional) | 🟡 | README §3.8, T3.7 |
| D31 | **Baseboard layout (T3.7), detail of D30:** 3 runners (2040 on edge, 520 mm, along X under the board, y 150 / 450 / 750), each fixed with 4 × M5×30 countersunk screws into drop-in T-nuts in the top slot; **bed posts = M5×45 stud from below + spring + nut on top of the panel** (turn the nut to level; the panel is 9 mm, so the nuts stand proud and the **steel sheet stops 24 mm short of the panel edge**, 352 × 432, still larger than A3); posts 15 mm from the panel corners; SK10s on M5×35 bolts with nut and washer under the board, the right rail's holes oversized (Ø7) for alignment; ZRIB mount centered between runners 1 and 2 at x 520. Y mounts stay un-drilled (D26). The layout is generated (`python -m plotzker layout`), not drawn by hand | 🟡 | T3.7, §6 |
| D32 | **Cable management (T3.8):** loose loom on printed support rails, not drag chains, for Y: a round loom (Ø8) folded in a U on the baseboard in the outboard strip beside the right Y belt, guided by an inner rail. X: ribbon festoon in the beam's rear T-slots (D33, trial after a mock-up; the other X options are in T3.8). Rejected: drag chains (more printed length), flat ribbon (custom connectors). Revisit if the loom drags or fatigues | 🟡 | T3.8 |
| D33 | **X cable: ribbon festoon in the beam's two rear T-slots (trial, T3.8).** A thin flat 6-conductor ribbon (servo + X endstop) runs in the lower slot (fixed run), makes a free U outside the face and returns in the upper slot (moving run) to a printed shoe on the carriage's rear block; the U moves at half the carriage speed; no tray or tension element. Mock-up first (ribbon ≤ 1.2 × 7.5 mm, stiff enough to be pushed through the slot). Fallbacks: flat ribbon in the gap behind the beam, or shorter X travel; drag chain and take-up pulley rejected (T3.8) | 🔬 Trial | T3.8 |
| D34 | **X belt attached at the bottom of the carriage (merged to master after the prototype; revert point: git tag `pre-x-belt-bottom` = the design with the belt at the top, `git checkout pre-x-belt-bottom`):** bridge under the beam, rear block behind it with the lower belt run clamped on its flat top (cap above); motor/idler axis lowered from z 93.8 to **70.7** (motor body 1 mm above the unclamped rear bolt heads: the motor mount clamps only the front bolt row, the idler mount only the rear row, so the endstop plug space is free); belt 3 mm further back (y 26) so the clamp nuts stay under a full roof on the block's 45° ramp; X− endstop board lies directly on the idler mount's foot (no pad part, no ±4 mm pad slots; trigger nut slot from the underside). Gantry height and brackets unchanged. Plastic: motor + idler mounts + pad 57.7 → 31.3 cm³, carriage +1.3 → net **−25 cm³** (−17 %) | 🟡 | T3.3, T3.4 |
| D35 | **Shelf under the X idler mount (T3.19):** the left bracket's base extends 10 mm outboard (`BRACKET.shelf_x` = −48, over the mount's footprint, y 16…62.5) so the mount's foot and end block rest on the bracket instead of hanging past its edge. Chosen over a thicker end block, gussets or a different print orientation, which barely helped while the overhang governed (plan §21). Costs 4.7 cm³ and 10 mm of bracket width; clearances checked in the assembly (nearest part: Y belt, ~5 mm) | ✅ | T3.19, plan §21 |
| D36 | **CAD split into `cadder` (generic framework) and `plotzker` (the plotter)** (T3.24). One repo for now; cadder is a uv workspace member (`cadder/`, its own `pyproject.toml`) and moves to its own repo later. cadder never imports a project; it has the whole generic vendor-hardware catalog; firmware stays in plotzker (the Marlin config script edits `#define`s, not CAD). A project registers parts, assemblies, assembly checks, FreeCAD assemblies, design checks and its own commands on a `Project`. Part classes: `Part` (any part), `MaterialPart` (material, optional FEM; plates, purchased parts), `PrintedPart` (print profile, build direction). cadder's docs are in `cadder/docs/` (FEM method, design diff, FreeCAD assemblies, sketch formats); the plotter keeps `docs/fem.md` (its parts and data) and `fem-subagent-plan.md` (its FEM history). Candidates to move with cadder later: the generic half of README §7, the `fem-analyst` agent, the generic Makefile targets | ✅ | T3.24, README §5 |
| D37 | **v1 pen holder (T3.6; numbered D29 until T3.24, an ID already taken):** one Ø6 rod (on hand) held by two printed arms; the pen slide rides on it in two printed sleeves (LM6UU is the later upgrade; the bores are laid out for it); a key rib on the plate, in a groove of the slide's lug, stops it turning. The FT90M (metal gears; chosen over the FS90) lies with its output facing the plate and the single-sided horn swinging in the gap behind its wall; the horn's M2 pin sits in a vertical slot of the lug, whose ceiling lifts the slide (pin down: the slide drops until the pen touches, the slot clearance is the float). Pen: 90° V-block with a yoke and an M5 thumbscrew; pen axis 16–22 mm in front of the carriage face. Rejected: flexure/four-bar (pressure not constant, long reach), plastic dovetail (stick-slip). Alternate if the sleeves stick: 625-bearing roller guide | ✅ | T3.6, §6 |

---

## 4. Inventory (parts on hand)

Working assumption: any **commonly available** 3D-printer / maker part can be obtained.
Parts listed here are ones we specifically plan around. If something turns out to be
hard to get, we adjust.

| Part | Qty | Details | Still to confirm |
|------|-----|---------|------------------|
| 2020 V-slot extrusion | several | **520 mm** long | — |
| 4020 V-slot extrusion | 2 | **520 mm** long → X beam; V-slot profile confirmed | End bores tapped M5 |
| 2040 V-slot extrusion | 3 | **520 mm** long → baseboard runners | — |
| Shorter 2020 / 2040 / 4040 extrusions | a few | e.g. 340 mm 2040 | Lengths |
| V-wheels | many | POM V-groove wheels on 625Z bearings (5 mm bore), Ø24 × 10 mm; eccentric spacers: 10 mm hex × 7.8, Ø7.1 × 2.1 boss, Ø5 bore, ~0.7 mm offset (2 needed, D21) | — |
| Ø10 mm smooth (optical-axis) shafts | 2 | **700 mm**, hardened → Y axis | — |
| SK10 shaft supports | 4 | End supports, shaft center **20 mm** above the mounting surface; 2 × M5 on 32 mm, 42 W × 37.5 H × 14 L ([`docs/hardware.md`](docs/hardware.md)) | — |
| SCS10UU linear bearing blocks | 4 | 2 per shaft; 35 L × 40 W × 26.5 H mm, shaft center 13 mm above the base, 4 × M5 top holes on 28 × 21 mm, top: two 10 mm raised flats (holes in them) with a 17 mm × 1 mm recess between, 92 g ([`docs/hardware.md`](docs/hardware.md)) | — |
| NEMA17 stepper motors | ≥ 3 (+1 for optional Z) | Standard 3D-printer type; sizes vary: typical 39.2 mm body / 22.6 mm shaft, short 33.5 / 19 | — |
| GT2 belt, pulleys, idlers | assorted | 6 mm belt (plenty); common 3D-printer 20T pulleys and idlers | Exact pulley/idler sizes (design for common, adjust) |
| Lead screws, linear bearings, misc. bearings | assorted | No LM6UU/LM8UU found yet | Only needed for a stepper Z experiment or the pen slide upgrade |
| Ø6 rod | 1 | ~200 mm, cuttable; the pen holder's rod needs 63 mm | — |
| Hobby servos | 2+ | **FeeTech FT90M** (metal gears, digital; used for the pen lift) and FS90 (spare); measured in `docs/hardware.md` | Horn thickness, spline height |
| **Controller: Zonestar ZRIB v5.8** | 1 | ATmega2560, 6 socketed StepStick drivers; **95 × 110 × 22 mm**, 4 × Ø3 holes 80 × 100 mm, out of its case ([`docs/controller.md`](docs/controller.md)) | X, Y, Z drivers: red A4988-type clones (photos); E0 to E2: white boards with M0–M2 pins (DRV8825 clone or LV8729-type, chip unread); red drivers' sense resistors unread; pin map (bench) |
| Controller: Creality Ender 3 V4.2.2 | 1 | STM32F103, 4 soldered drivers (X, Y, Z, E0), 3 endstop inputs + probe pin, 24 V; fallback ([`docs/controller.md`](docs/controller.md)) | MCU and driver chip markings; bootloader; PSU voltage |
| BigTreeTech TFT35-E3 | 1 | Touch screen with its own MCU; **not a motion controller**. Optional UI and SD/USB G-code sender | Hardware version |
| Power supply | 1 | **Cheng Liang P360W24V: 24 V, 15 A max (360 W)**; **215 × 113 × 50 mm** (user) | Mounting holes, terminal side |
| Endstop switches | ≥ 3 | Creality-type boards: 20 × 19 × 1.5 mm, M3 holes 15 mm apart at the rear, switch across the front edge, lever 5 mm out at rest / 1.5 mm pressed, connector 10 × 7.2 × 5.6 mm with 2 mm past the rear edge (`docs/hardware.md`) | Click point, lever length |
| Wood screws | many | **4 × 25 mm, countersunk** (the shortest on hand); printed parts use 9 mm bosses so they don't reach through the 18 mm plywood | Head diameter (assumed 8 mm) |
| M5 hardware for the baseboard | to buy | 12 × M5×30 countersunk + 12 drop-in T-nuts (runners); 8 × M5×35 + nuts + washers (SK10s); 4 × M5×45 + washers, nuts and springs Ø9 × 12 (bed posts); common sizes | T-nut thickness and slot lip (*assumed* 4 / 1.8) |
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
| Baseboard | 18 mm plywood, 700 × 900 mm; runners (2040 on edge) at y 150 / 450 / 750, x 90–610; 28 holes in `docs/baseboard-holes.md` |
| Bed | Panel 400 × 480 × 9 on 4 posts (x 165 / 535, y 225 / 675), steel 352 × 432 × 0.8; top ~14.8 mm; post nuts up to z 22.7 |
| Y loom | Ø8, R 16; lying length 666 mm; hole (690, 150); rails wall at shaft + 42; fold apex y 781 at the back end |
| Pen reach (10 mm pen) | x 150–576, y 138–683 (A3 centered: x 201–499, y 240–660) |
| Shaft spacing | 520 mm |
| Y belt | 30 mm outboard of each shaft; motor/idler axis ~26.8 mm above the baseboard; idler axle y 31, motor axis y 800 (machine frame); ~1.5 m belt per side |
| X belt | Vertical loop behind the beam, center 26 mm behind the beam's center plane; motor/idler axis ~70.7 mm above the baseboard (D34); ~1.2 m belt |
| Carriage | Wheels 64 mm apart; front face 21.3 mm in front of the beam center; bottom 33.15, top 122.85 mm above the baseboard |
| Pen holder | Lift 7 mm / float 3 mm; rod Ø6 × 63 mm; slide 45 mm; pen axis 16–22 mm in front of the carriage face; head depth ~39 mm (servo front), up to z ~105 |
| Tool-plate interface | 50 W × 45 H, bottom edge at 33.15 mm; hook groove at the top; 2 × M3 nuts 36 mm apart |
| Mechanics footprint | ~600 × ~800 mm |

`python -m plotzker check` prints the current values from `params.py`.

---

## 6. As-built design notes

Dimensions and details of the parts designed so far. The principles behind them are in
README §3; the exact values live in `params.py`.

**Belt lines:** each Y side has its own belt **30 mm outboard of its shaft** (motor at
one end, idler at the other, ~1.4 m belt each). The top run is cut and both ends clamp
under the gantry end bracket; the belt line puts the Y motor shaft and idler axle at
**~26.8 mm** above the baseboard. The **X belt** is a vertical loop behind the beam (belt
center 26 mm behind the beam's center plane, ~1.2 m of belt); its lower run is cut and
clamped on top of the carriage's rear block (cap above the belt, M3 down into nuts in the block).
X motor shaft and idler axle run front-to-back at **~70.7 mm** above the baseboard (D34).
**Belt clamps (D27):** one cap design (`belt_clamp.py`) for all six clamps. The gantry
brackets and the carriage's rear block have **flat undersides** (no printed channel or
bridge); the cap has the groove (between two 1.08 mm rails) that guides the belt, ridges in
the tooth gaps, and M3×14 screws into M3 nuts pressed into the bracket / block (hex shafts from the top on
the brackets, a slot from the back on the carriage).
**Handles (D28):** the gantry end bracket exposes `block_bolts_front_0..3`, `block_bolts_rear_0..3`, `beam_bolts_0..1`, `belt_clamps_0..1` (front, rear) and `trigger_screw`; the belt clamp exposes `mount` (rail tops). `gantry_end_local` aligns the screws, clamps and belt pieces to them. PythonSCAD carries a handle through `translate`, `mirror` and boolean operations, but only if it is a matrix attribute (not a list of them; hence the numbered names) and not through `fillet`.

**Y drive (T3.5):** per side, the motor sits **behind the rear SK10** with its shaft
pointing outboard (body inboard, ≥ 3 mm from the SK10; `y_motor_mount.py`: 5 mm plate, foot
extending outboard so the wood screws stay accessible, two gussets). The idler is **in front
of the front SK10** (T3.17): `y_idler_mount.py` is the foot with a dovetail rail and screw block
built in, `y_idler_slider.py` carries the idler on an M5 axle held by both arms and is pulled
forward by an M3 screw from the block at the front (8 mm travel; the head is reachable from the
front). The **Y endstop**
board stands on a tower on the foot, in the plane of the bracket's trigger screw, front edge toward +y: the screw tip presses
the lever toward the board ~2.2 mm before the end of travel (the screw length sets the trip point). All
mounts are screwed down with 4 × 25 countersunk wood screws through 9 mm bosses on the feet; the right-hand parts are mirror images, except the tower (the board is chiral).
Each mount's foot also carries an **SK10 pocket** (`parts/sk10_pocket.py`, D26): a corner cut-out the
SK10's base sits in (4 mm × 24 mm end-wall finger against the shaft-end face, outboard side wall; open
toward the inboard side and the other SK10), so the mounts are fitted last, pushed into the corner of
the aligned SK10s.

**X drive (T3.4):** the **X motor** sits behind the beam at the right end
(`x_motor_mount.py`), the **idler + belt tensioner** at the left end (T3.16: `x_idler_mount.py` is
the foot with a dovetail rail and screw block built in; `x_idler_slider.py` carries the idler on an
M5 axle held by both arms and is pulled outboard by an M3 screw, 8 mm of travel),
with the **X− endstop** board lying on the idler mount's foot (the trigger head presses the lever along the board).
Both mounts sit on the gantry bracket over the rear SCS block and are clamped by that
block's M5 bolts (M5×25 on the clamped row: the rear row for the idler, the front row for the motor; the other row stays M5×20), so the brackets need no extra holes.

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
(D21), all on M5×42 bolts (washer and head in 2 mm counterbores on the front face). A bridge under the middle of the beam (between the bottom wheels) carries
a rear block behind the beam that clamps both ends of the X belt's lower run (same clamp caps as Y) and
holds the X endstop trigger (M3 screw head, pointing −X). Printed front face down, ~64 g.

**Baseboard and bed (T3.7, D30, D31):** the plywood (700 × 900 × 18) carries, on top, the SK10s
(M5×35 bolts, nuts and washers underneath), the Y mounts (wood screws, not pre-drilled) and the bed
panel on four posts; underneath, three 2040 runners on edge (feet, 40 mm tall) and the ZRIB mount
(39 mm drop). A post is an M5 stud whose head and washer sit under the board; a spring (Ø9 × 12,
compressed to the 5 mm gap) pushes the panel up against a washer and nut on top, which sets the
corner height (gap 2–8 mm). The panel's top-face nuts are why the steel stops short of the edge.
The ZRIB mount sits between runners 1 and 2 (95 mm gap each side of its footprint) so the board's
rear edge (USB, DC, SD) faces runner 2; reach it from the right side of the machine. Everything
the drilling needs is in `params.BASEBOARD`; `layout.py` turns it into the SVG and the hole table.

**v1 pen holder (T3.6, D37):** two printed parts. The **body** (`pen_holder_body.py`) is a
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
