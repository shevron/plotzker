# DIY Pen Plotter

A 2D CNC pen plotter built mostly from parts salvaged from low-end 3D printers, standard
hardware (metric hex fasteners, bearings) and 3D-printed parts. It draws with ordinary
household pens on paper, card, cardboard or thin wood.

> **Status:** Phase 1 (architecture) complete. Phase 3 in progress: T3.1–T3.4 done (CAD
> scaffold, gantry end brackets, X carriage, X motor/idler/endstop mounts; STLs in `stl/`,
> test prints pending). CAD migrated from OpenSCAD to PythonSCAD (T3.9, D22; identical
> STLs). On trial: SVG 2D sketches for profiles (D23; V-slot 2020/2040). Open: Q12 (beam ends tapped?). Q10 (SVG/PDF toolchain) deferred until the
> machine runs.
> **Next:** T3.5 Y motor mounts, idlers, tensioners and Y endstops. Phase 2 can
> run in parallel. See the **work plan in §8**; CAD workflow in **§10**.

**Contents:** 1 Requirements · 2 Inventory · 3 Build phases · 4 Design · 5 Key numbers ·
6 Decision log · 7 Open questions · 8 Work plan · 9 Repository layout ·
10 CAD workflow

Detailed docs: [`docs/controller.md`](docs/controller.md) (board, pin map, firmware plan) ·
[`docs/hardware.md`](docs/hardware.md) (vendor part dimensions for CAD)

---

## 1. Requirements and constraints

| # | Requirement | Notes |
|---|-------------|-------|
| R1 | Move a pen in X/Y over a **flat** work surface | Paper is the primary medium |
| R2 | Support media **0–15 mm** thick | Paper (~0.1 mm) up to cardboard / thin wood |
| R3 | **Work area: A3 (297 × 420 mm) and smaller** | Travel ≥ 320 × 440 mm for margins and registration |
| R4 | Lift and lower the pen under program control | Required in v1; without it every path is connected |
| R5 | Hold standard pens of **7–16 mm** diameter | Manual pen insertion in v1 |
| R6 | Constant, gentle pen pressure despite small height errors | Pen head absorbs ±1.5 mm (§4.8) |
| R7 | Modular, easily replaceable tool head | Path to automatic pen changing, other tools later |
| R8 | Use parts on hand wherever possible; otherwise commonly available parts | §2 |
| R9 | Open-source firmware and toolchain | Marlin; no custom firmware |

**Project constraints (hard rules, see also `CLAUDE.md`):**
- All measurements **metric**.
- Hardware is off-the-shelf (metric hex fasteners etc.) or common low-end 3D-printer
  parts (steppers, belts, lead screws, bearings, extrusions), plus 3D-printed parts.
- CAD in **PythonSCAD** (Python package `plotter_cad`), parametric (D2, D22).
- Safety: printer heaters disabled in firmware and left unconnected; mains wiring
  enclosed and earthed.

Non-goals (for now): cutting, engraving, lasers, high-speed operation, enclosure.

---

## 2. Parts on hand (inventory)

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
| Endstop switches | ≥ 3 | Creality-type boards: 20 × 19 mm (27 mm incl. lever), 2 holes 15 mm apart, ~12 mm thick incl. connector | Screw size (M3?), hole positions |
| Plywood, steel sheet, magnets | to buy/cut | Baseboard, bed panel, work holding (§4.8) | — |

---

## 3. Build phases

| Phase | Name | Output | Status |
|-------|------|--------|--------|
| 0 | Inventory & requirements | §1, §2 | ✅ Done |
| 1 | Architecture decisions | §4, §6 | ✅ Done |
| 2 | **Electronics bench bring-up** | Marlin configured and flashed; pin map verified; motors, endstops and servo working on the bench | Next |
| 3 | **Mechanical CAD (PythonSCAD)** | Parametric model: gantry, carriage, mounts, v1 pen holder, baseboard layout | 🔧 In progress |
| 4 | Print & assemble | Baseboard, Y axis, gantry, X axis, wiring | — |
| 5 | Integration & calibration | Homing, squaring, steps/mm, soft limits, bed leveling | — |
| 6 | First plots & pen-lift experiments | Test patterns from hand-written/scripted G-code; pen-lift mechanism chosen (Q6) | — |
| 7 | Software toolchain | SVG/PDF → G-code workflow (Q10) | Deferred |
| 8 | Enhancements | Automatic pen change, other tools, TFT35 standalone use | — |

Phases 2 and 3 are independent and can run in parallel.

---

## 4. Design

### 4.1 Kinematics: Cartesian, not CoreXY (D5)

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

### 4.2 Axis layout (D6, D7, D12, D13)

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
  V-wheels.
- **Drive:** GT2 belts on both axes. Typical setup: 20T pulley, 1.8° motor, 1/16
  microstepping → **80 steps/mm**. Each Y side has its own belt **30 mm outboard of
  its shaft** (motor at one end, idler at the other, ~1.4 m belt each). The top run is cut
  and both ends clamp under the gantry end bracket; the belt line puts the Y motor shaft and
  idler axle at **~27.8 mm** above the baseboard. The **X belt** is a vertical loop behind
  the beam (belt center 23 mm behind the beam's center plane, ~1.2 m of belt); its top run is
  cut and clamped under the carriage's rear block, ~3.6 mm above the beam top. X motor shaft
  and idler axle run front-to-back at **~94.8 mm** above the baseboard.
- **X drive (T3.4):** the **X motor** sits behind the beam at the right end
  (`x_motor_mount.py`), the **idler + belt tensioner** at the left end (`x_idler_mount.py`:
  the M5 axle slides in an 8 mm slot, an M3 screw pushes it outward, the axle nut locks it),
  with the **X− endstop** on top of the idler mount (`x_endstop_mount.py`, ±4 mm slots).
  Both mounts sit on the gantry bracket over the rear SCS block and are clamped by that
  block's 4 M5 bolts (M5×25 there instead of M5×20), so the brackets need no extra holes. Lead screws only for an
  optional pen-Z experiment.
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

SK10 clamps sit in between: expect **0.2–0.4 mm**. The pen head absorbs it (§4.8).
**Keep the gantry light.** If sag ever shows up, supported rails (e.g. SBR12) can
replace the shafts on the same layout.

**Shaft alignment:** closed bushings jam when the shafts aren't parallel. Fix one shaft;
mount the second with slightly oversized SK10 holes; move the gantry to each end and
tighten the supports there, so the gantry aligns the shafts itself.

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

**Work area:** A3's short side (297 mm) runs across X, the long side (420 mm) along Y.
- **X travel ≈ 426 mm** (520 mm beam − ~70 mm carriage − 2 × 12 mm end keep-out: in front
  of the beam the tool head can't pass over the SCS blocks).
- **Y travel ≈ 540 mm** (700 mm − 2 × 14 mm SK10 − ~120–135 mm gantry end). It covers
  A3 with room to park the gantry off the sheet while loading.
- Shaft spacing **520 mm** center to center (beam end over each shaft, T3.2).
- Footprint of the mechanics ~600 (X) × ~800 (Y) mm; Y motors/idlers set the Y length (T3.5).

### 4.3 Pen lift and media thickness (D14, D18)

**Approach: choose the pen-lift mechanism by experiment.** The v1 pen holder (§4.4) has a
vertical slide whose lift actuator can be swapped. Candidates are compared on real plots
in phase 6.

**Requirements every candidate must meet:**
- **Constant, adjustable pen pressure**: starting point ~20–80 g at the tip (fineliners
  need less, markers more), independent of media thickness and small height errors.
- **≥ 3 mm of float** below first contact with near-constant pressure, to absorb ±1.5 mm
  of shaft sag, bed and media unevenness (§4.8).
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

### 4.4 Tool head and modularity (D8)

A **custom 3D-printed X carriage** with a defined **tool-plate interface** on its front face.
Every tool head (v1 pen holder, pen-lift experiments, future pen changer) is a separate
printed part. Start simple and evolve; the tool head is expected to be replaced.

**X carriage:**
- Rides on the upright 4020 beam: 2 V-wheels in the top groove, 2 in the bottom groove
  (**eccentric spacers on the bottom pair** for preload, D21; only 2 needed). Fallback if
  2 can't be found: slotted axle holes with an M3 push screw, locked by the axle nut.
- Integrates the X belt clamp, the X endstop trigger, and strain relief for the tool-head cable.

**Tool-plate interface v1:**
- **Hook + 2 × M3:** a French-cleat hook along the top of the interface carries and
  locates the tool head: the carriage has a groove with a 45° undercut (6 mm opening, 3 mm
  deep), closed at both ends so it also locates the tool in X; the tool plate's lip drops
  into it. Two M3 screws into heat-set inserts on the lower edge clamp it (36 mm apart,
  7 mm above the bottom edge). Fast to swap and repeatable.
- **Tool plate envelope:** ≤ 50 mm wide (it sits between the bottom wheels' bolt heads);
  interface 45 mm tall, bottom edge level with the carriage bottom.
- **Electrical:** one connector on the carriage for the tool head, in a 16 × 8 mm window in
  the carriage's top tab: 3-pin servo in v1, with space for a 4–6 pin connector later
  (solenoid, sensor, pen-changer signals). Zip-tie slots below it for strain relief.
- **Keep the pen close:** pen axis within ~25 mm of the carriage face, tip close below
  the beam.
- Exact dimensions live in `params.py`.

**X carriage (T3.3, `parts/x_carriage.py`):** an 8 mm front plate with 4 V-wheels
64 mm apart: top pair on printed 8.3 mm stand-offs, bottom pair on the eccentric spacers
(D21), all on M5×35. A bridge over the middle of the beam (between the top wheels) carries
a rear block behind the beam that clamps both ends of the X belt (same clamp caps as Y) and
holds the X endstop trigger (M3 screw head, pointing −X). Printed front face down, ~64 g.

**v1 pen holder:** a printed body on the interface with a vertical slide carrying a V-groove
pen clamp (centers 7–16 mm pens on one axis; thumbscrew or strap), a coarse ~20 mm height
adjustment, and a mount for the servo (gravity + servo first).

**Not for v1:** a vertical extrusion "spine" (e.g. the 340 mm 2040). The pen needs only
a few mm of stroke; an extrusion adds mass and leverage. It could become its own tool head
later for a heavy tool needing a long Z.

**Later:** automatic pen changing (parking slots at the edge of the work area, or a
carousel). The interface and connector leave room for it.

### 4.5 Controller and firmware (D9, D19)

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

### 4.6 Power

- Re-use the printer PSU; **voltage to be read from the label** (the board accepts 12–24 V).
  With no heaters, three to four steppers draw far below a printer PSU's rating.
- The servo runs from the ZRIB's buck 5 V regulator. Check during bring-up that the board
  doesn't reset when the servo stalls. If it does, add a separate 5 V buck converter
  (common GND).
- Mains: enclosed terminals, earthed PSU and frame, strain relief, switched inlet.

### 4.7 Homing, limits and coordinates

- **Origin at front-left** (X−, Y−). Homing order: Y (both sides square the gantry), then X.
- Endstops: X−; Y− (left) and the Y+ input used as the right-side Y2 endstop. Z− only if
  a stepper Z is used.
- Max limits by firmware soft limits (`X_MAX_POS`, `Y_MAX_POS` from the measured travel).
- After homing, the plot origin is set relative to the registration corner (§4.8),
  e.g. with `G92` or a workspace offset.

### 4.8 Frame, bed and work holding (D16, D17)

**Principle: one flat reference.** The SK10 supports and the bed mount on the **same
baseboard**. The bed only needs to be parallel to the plane the pen moves in, not level
with gravity.

**Baseboard:**
- **18 mm plywood** (birch/multiplex), about **850 × 650 mm**: the mechanics plus room for
  electronics.
- **Extrusion runners** (2040/2020 offcuts) screwed across the underside, perpendicular
  to the shafts. They stop the board bowing, act as feet, and leave space underneath for
  the PSU and wiring.
- Electronics: the ZRIB (in its metal bracket) and the PSU under the board between the
  runners, or along the rear edge behind the Y motors. Driver cooling fan.
- Cables moving with the gantry (X motor, X endstop, tool head): printed drag chain or a
  loose loom.

**Bed:** a separate **bed panel** (6–9 mm plywood/MDF) with a **0.5–1 mm galvanized steel
sheet** bonded on top. Flat magnets hold the media anywhere, and nothing at the sheet
edges can catch on the head. The panel sits on **4 adjustment points** (M5 screws with
nuts, or springs and thumb-nuts) above the baseboard. Alternative: 3–5 mm cast acrylic
with clips. Glass isn't needed.

**Leveling (once, then occasionally):** a dial gauge, feeler gauge or sheet of paper under
the pen holder. Jog to the four corners and the center, and adjust until the gap is
within ±0.3 mm.

**Z error budget the pen head must absorb:**

| Source | Estimate |
|--------|----------|
| Shaft sag (mid-span vs ends) | 0.2–0.4 mm |
| Bed flatness after adjustment | ±0.3 mm |
| Residual board/panel bow | ~0.3 mm |
| Media unevenness (warped card, wood) | 0.5–1.5 mm |
| **Total** | **~±1.5 mm** → ≥ 3 mm float, ≥ 5 mm lift (§4.3) |

**XY squareness and registration:**
- Dual Y endstops square the gantry at every homing. X-to-Y squareness is set once when
  mounting the beam on its end brackets, and checked by plotting a large square and
  comparing diagonals.
- **Registration corner:** the machine draws an L-shaped reference line at the sheet
  origin. Fix printed or magnetic stops along it so sheets go in square to the machine axes.

### 4.9 Software (Q10 deferred)

**First (phases 5–6):** hand-written or small scripted G-code test patterns (squares,
circles, grids, pen up/down tests), sent over USB (Pronterface / any Marlin host) or from
the SD card.

**Later (Q10):** an SVG/PDF → G-code workflow. Likely candidates: Inkscape or generative
code → `vpype` (merge, sort, simplify paths) → G-code with pen up/down mapped to `M280`
(or to the chosen pen-lift commands) → sender.

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
| Y belt | 30 mm outboard of each shaft; motor/idler axis ~27.8 mm above the baseboard |
| X belt | Vertical loop behind the beam, center 23 mm behind the beam's center plane; motor/idler axis ~94.8 mm above the baseboard; ~1.2 m belt |
| Carriage | Wheels 64 mm apart; front face 21.3 mm in front of the beam center; bottom 33.15, top 122.85 mm above the baseboard |
| Tool-plate interface | 50 W × 45 H, bottom edge at 33.15 mm; hook groove at the top; 2 × M3 inserts 36 mm apart |
| Mechanics footprint | ~600 × ~800 mm |

---

## 6. Decision log

| ID | Decision | Status | Ref |
|----|----------|--------|-----|
| D1 | Metric units throughout | ✅ | Project rule |
| D2 | CAD in PythonSCAD (Python), parametric; OpenSCAD until D22 | ✅ | Project rule, D22 |
| D3 | Off-the-shelf / 3D-printer parts + printed parts only | ✅ | Project rule |
| D4 | Pen lift is a v1 requirement | ✅ | §4.3 |
| D5 | Cartesian moving-gantry layout (not CoreXY) | ✅ | §4.1, Q4 |
| D6 | Y = 2 × Ø10 × 700 mm shafts on SK10 supports, 2 SCS10UU blocks per side | ✅ | §4.2; replaces the earlier SBR12 plan (no SBR12 on hand) |
| D7 | GT2 belt drive on X and Y; lead screws only for an optional pen-Z experiment | ✅ | §4.2 |
| D8 | Printed X carriage with a hook + 2 × M3 tool-plate interface and a tool-head connector; tool heads are separate printed parts; no extrusion spine in v1 | ✅ | §4.4, Q8 |
| D9 | Controller: ZRIB v5.8 with Marlin `BOARD_ZRIB_V53`; Y2 on E0; servo on SERVO0 | ✅ | §4.5, Q7; pin map verified in phase 2 |
| D10 | Target media A3 and smaller; A3 short side across X | ✅ | Q3 |
| D11 | Y travel ~540 mm; Y length parametric in CAD | ✅ | Q3 |
| D12 | X beam: 520 mm 4020 V-slot mounted upright (~426 mm X travel) | ✅ | §4.2 |
| D13 | Dual Y motors with one endstop per side (auto-squaring) | ✅ | §4.2, Q5 |
| D14 | Pen-lift mechanism chosen by experiment; start with gravity + servo | ✅ | §4.3, Q6 |
| D15 | Media thickness 0–15 mm | ✅ | Q3 |
| D16 | 18 mm plywood baseboard (~850 × 650 mm) with extrusion runners underneath; shafts and bed share it as the reference | ✅ | §4.8, Q9 |
| D17 | Bed: adjustable panel (4 points) with a bonded steel sheet and magnets; acrylic as alternative; no glass | 🟡 Proposed (final choice at build) | §4.8 |
| D18 | Pen head absorbs ±1.5 mm Z error: ≥ 3 mm float with near-constant pressure, ≥ 5 mm lift | ✅ | §4.8 |
| D19 | Heaters disabled in firmware (`EXTRUDERS 0`, sensors 0) and left unconnected | ✅ | §4.5 |
| D20 | SVG/PDF toolchain deferred; prove the machine with hand-written/scripted G-code first | ✅ | §4.9, Q10 |
| D21 | X-carriage preload: 2 eccentric spacers on the bottom wheel pair. Fallback if 2 can't be found: slotted axle holes + M3 push screw, clamped by the axle nut (`CARRIAGE.preload` in `params.py`) | ✅ | §4.4, Q11 |
| D22 | Migrate the CAD from OpenSCAD to PythonSCAD: a `plotter_cad` Python package (`src/`), pip `pythonscad` module for STL export, PythonSCAD app for renders/preview. Ported 1:1 (all 8 STLs geometrically identical); the old `.scad` files were removed afterwards | ✅ | §10, T3.9 |
| D23 | **Experiment:** 2D sketches as SVG files next to the module that extrudes them (sketch → extrude workflow), loaded with `geometry.load_sketch()`. First use: the V-slot 2020/2040 profiles (`hardware/vslot_2020.svg`, `vslot_2040.svg`). PythonSCAD stays the only 3D source; printable parts stay fully parametric in Python for now | 🔬 Trial | §10 |

---

## 7. Open questions

| ID | Question | Status |
|----|----------|--------|
| Q1 | Controller boards | ✅ ZRIB v5.8; Creality board TBD (fallback); TFT35-E3 is a screen/SD sender |
| Q2 | Parts inventory | ✅ Enough to proceed; remaining measurements listed in §8 (T2.1, T3.1) |
| Q3 | Work area, rail length, media thickness | ✅ A3; ~540 mm Y travel; 0–15 mm media |
| Q4 | Cartesian vs CoreXY | ✅ Cartesian |
| Q5 | Gantry drive and squaring | ✅ Dual Y motors + dual endstops |
| Q6 | Pen lift and thickness handling | 🔬 Approach decided; mechanism chosen by experiment (T6.2) |
| Q7 | Firmware and board mapping | ✅ Marlin `BOARD_ZRIB_V53`; verified in T2.3 |
| Q8 | Tool-plate interface and v1 pen holder | ✅ §4.4 |
| Q9 | Frame, baseboard and work holding | ✅ §4.8 (bed material finalized at build) |
| Q10 | SVG/PDF → G-code toolchain | ⏸ Deferred to phase 7 |
| Q11 | X-carriage wheel preload | ✅ D21: 2 eccentric spacers on the bottom pair; slot + push-screw fallback |
| Q12 | Are the 4020 beam ends tapped M5 (gantry brackets bolt into the end bores)? | ❓ User to check; else tap M5 or let an M5 screw cut its own thread |

---

## 8. Work plan

Tasks are sized for one working session each. When a task is done: tick it here, record
any new decisions in §6, and update the status line at the top.

### Phase 2 — Electronics bench bring-up (see `docs/controller.md`)

- [ ] **T2.1 Read the hardware facts.** PSU label (voltage, current); chip markings on all
  6 drivers (A4988/DRV8825/other); microstepping jumpers under each socket; servo model.
  *Done when:* recorded in §2 and `docs/controller.md`.
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

### Phase 3 — Mechanical CAD (PythonSCAD; conventions in `CLAUDE.md`, workflow in §10)

- [x] **T3.1 Scaffold the CAD.** `params.py` (travel, shaft spacing, clearances,
  print tolerances, tool-plate interface dimensions), `hardware/` (models of NEMA17,
  GT2 pulley, SK10, SCS10UU, 2020/4020, V-wheel, fasteners, from `docs/hardware.md`).
  Measure first: SK10 hole spacing/size, NEMA17 body length, belt width, V-wheel dimensions.
  - [x] Files written with catalog values marked `// ASSUMED`; derived stack-up, travel
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
  bottom to ~58 mm (§4.2). Bracket bears on the SCS10UU's two 10 mm top flats (measured).
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
- [ ] **T3.5 Y motor mounts, Y idlers and belt tensioners** (on the baseboard, in line with
  each shaft); endstop mounts for X−, Y−, Y2. Belt center 30 mm outboard of each shaft;
  motor shaft / idler axle at `y_pulley_axis_z` (~27.8 mm, motor body ~6.7 mm above the
  board). Y endstops are hit by the bracket's trigger screw (outboard, ~48 mm above the
  board). Endstops: Creality-type boards (`endstop()` in `hardware/`). *Check first:*
  screw size (M3?) and where the two holes sit (across the 20 mm width?).
- [ ] **T3.6 v1 pen holder (tool head).** Vertical slide, V-groove clamp for 7–16 mm pens,
  ~20 mm height adjustment, servo mount, gravity loading with room for added weight; meets
  the §4.3 requirements. Interface: `TOOL_PLATE` in `params.py` (≤ 50 mm wide, hook lip for the
  45° groove, 2 × M3); cable to the connector window in the carriage top tab.
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

### Phase 4 — Build

- [ ] **T4.1** Cut the baseboard and bed panel; fit the runners; drill from the T3.7 layout.
- [ ] **T4.2** Mount the SK10s and shafts; fit the gantry; align the shafts (§4.2 procedure).
- [ ] **T4.3** Fit the beam, carriage, motors, belts and endstops; check that the axes move
  freely by hand.
- [ ] **T4.4** Mount the electronics and PSU; wire everything; safety checks on mains wiring.

### Phase 5 — Integration & calibration

- [ ] **T5.1** First homing (Y squaring, then X); set soft limits from the measured travel.
- [ ] **T5.2** Steps/mm check (draw/measure a 300 mm line); squareness check (diagonals of a
  large square); belt tension.
- [ ] **T5.3** Bed leveling (§4.8); set the pen-down height and the float.

### Phase 6 — First plots & pen-lift experiments

- [ ] **T6.1** Test-pattern G-code in `software/test-patterns/` (squares, circles, grids,
  text, pen up/down stress test); speed/acceleration tuning.
- [ ] **T6.2** Pen-lift experiments (Q6): gravity + servo, then spring + servo and
  solenoid/magnet options; compare pressure consistency, line quality and speed; record the
  results in `docs/pen-lift.md` and choose a mechanism.
- [ ] **T6.3** Registration corner (§4.8).

### Phase 7 — Software toolchain (Q10)

- [ ] **T7.1** Choose and document the SVG/PDF → G-code workflow.

### Phase 8 — Enhancements (backlog)

- Automatic pen changing; TFT35 standalone plotting; other tool heads.

---

## 9. Repository layout

```
Plotter/
├── README.md            ← overview, decisions, work plan (this file)
├── CLAUDE.md            ← guidelines for Claude working on this project
├── pyproject.toml       ← Python project: plotter_cad package, deps, pytest/ruff/uv config
├── Makefile             ← shortcuts: make develop / check / format / lint / test / stl / render / clean
├── uv.lock              ← locked dependency versions (uv)
├── .python-version      ← Python version for pyenv and uv (3.14)
├── docs/
│   ├── controller.md    ← ZRIB v5.8 analysis, pin map, bring-up checklist
│   └── hardware.md      ← vendor part dimensions for CAD
├── src/plotter_cad/     ← CAD (PythonSCAD); paths in this README are relative to it
│   ├── params.py        ← shared parameters, derived values, design checks
│   ├── geometry.py      ← $fn settings, teardrop holes, SVG sketch loader and other helpers
│   ├── hardware/        ← vendor-part dimensions and models (SK10, SCS10UU, NEMA17…),
│   │                      plus SVG sketches of profiles (vslot_2020.svg, vslot_2040.svg)
│   ├── parts/           ← printable parts, one module each (print orientation)
│   ├── assemblies/      ← fit-check assemblies (gantry, carriage, skeleton, gallery)
│   └── build.py         ← CLI: python -m plotter_cad {check,stl,render,all}
├── tests/               ← pytest: design checks, key numbers, part reference geometry
├── stl/                 ← exported printable parts (generated by `make stl`; git-ignored)
├── renders/             ← PNG renders of parts and assemblies (generated by `make render`; git-ignored)
├── firmware/            ← Marlin configuration and build notes
└── software/            ← test patterns, toolchain scripts
```

---

## 10. CAD workflow (PythonSCAD)

The CAD is plain Python on top of the [PythonSCAD](https://pythonscad.org) `pythonscad`
module (OpenSCAD's geometry engine with a Python API). Conventions: `CLAUDE.md`.

**Setup (once):** Python ≥ 3.14 from [pyenv](https://github.com/pyenv/pyenv), packages
managed with [uv](https://docs.astral.sh/uv/). `.python-version` pins 3.14 for both
tools; `[tool.uv] python-preference = "only-system"` in `pyproject.toml` makes uv use the
pyenv interpreter instead of downloading its own. Dependencies are locked in `uv.lock`.

```bash
cd Plotter
pyenv install --skip-existing 3.14            # any 3.14.x
uv venv --python "$(pyenv which python)"      # creates .venv on the pyenv interpreter
uv sync --extra dev                           # plotter_cad + pythonscad + pytest + ruff
source .venv/bin/activate                     # or prefix commands with `uv run`
```

`make develop` runs these steps. After changing dependencies in `pyproject.toml`, run it
(or `uv sync --extra dev`) again; it updates `uv.lock`.

**Shortcuts (`Makefile`):** `make develop` (set up the environment), `make check` (ruff
lint + format check, changes nothing), `make format` (re-format the code), `make lint`
(ruff lint with automatic fixes), `make test` (pytest), `make stl` (all STLs), `make render` (all PNG renders; needs the PythonSCAD app), `make clean` (delete
`stl/`, `renders/`, caches and build output; keeps `.venv`). `make` lists them.

For renders and interactive preview, also install the PythonSCAD app
(pythonscad.org/downloads; on macOS it is found at `/Applications/PythonSCAD.app`).

**Commands:**

| Command | What it does |
|---------|--------------|
| `python -m plotter_cad check` | Design checks + key numbers (§5) |
| `python -m plotter_cad stl [names]` | Export printable parts to `stl/` |
| `python -m plotter_cad render [names]` | PNGs of parts and assemblies to `renders/` (needs the app; `--pythonscad PATH` or `$PYTHONSCAD`) |
| `python -m plotter_cad all` | All of the above |
| `python -m pytest` | Tests: design rules, §5 numbers, every part builds flat on the bed and matches `tests/reference_parts.json` |
| `ruff format . && ruff check .` | Formatting and lint (PEP 8) |

After an intentional geometry change: review the new STLs/renders, then
`python -m pytest --update-reference`.

**2D sketches (experiment, D23):** a shape that is easier to draw than to code can be an
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

**Interactive preview:** open `preview.py` (repo root) in the PythonSCAD app, set the
part or assembly name at the top, and render (F6). It adds `src/` to the path itself.
