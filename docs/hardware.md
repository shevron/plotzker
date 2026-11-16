# Hardware reference dimensions

Vendor-part dimensions we design around. These values go into `src/plotter_cad/hardware/` (one frozen `*Spec` dataclass per part).
All in mm.

## SCS10UU linear bearing block (Y axis, 4 pcs)

Source: the SCS10UU row of a vendor dimension table (SCS…UU series; the table itself is
not kept in the repository), plus the user's measurements where noted.

| Symbol | Value | Meaning (from the drawing) |
|--------|-------|----------------------------|
| d | 10 | Shaft diameter (LM10UU bushing inside) |
| h | 13 ±0.02 | Shaft center height above the block's base |
| E | 20 ±0.02 | Shaft center to the block's side (= W / 2) |
| W | 40 | Overall width (across the shaft) |
| L | 35 | Length (along the shaft) |
| F | 26 | Overall height. **Measured by user: 26.5**; use the measured value and check in CAD |
| G | 21 | Height of the narrower upper body (above the base flange step) |
| T | 8 | Thickness of the top mounting section |
| K | 6 | Top mounting-hole center to the block's side (= (W − B) / 2) |
| B | 28 ±0.2 | Top mounting-hole spacing **across** the shaft |
| C | 21 ±0.2 | Top mounting-hole spacing **along** the shaft |
| S1 | 4 × M5 | Threaded holes in the top face (thread depth ≈ L1) |
| L1 | 12 | Depth of the S1 threads |
| S2 | 4 × Ø4.3 | Through holes for M4 bolts from below (base mounting) |
| Bushing | LM10UU | Basic load rating 372 N dynamic / 549 N static |
| Mass | 92 g | Each |

The top face of our blocks is not flat: see the top-face note under the stack-up below.

**For the gantry:** the gantry end brackets bolt to the **top face** using the 4 × M5
threaded holes on a **28 × 21 mm** pattern (M5 × ≤ 12 mm thread engagement into the block,
so bracket thickness + 10 mm screw length works well).

## SK10 shaft support (Y axis, 4 pcs)

Source: the SK10 row of a vendor dimension table (supplied by user; the table itself is
not kept in the repository). Shape: a 42 mm wide base flange with one mounting hole each
side of an 18 mm wide upright body; the body is slit above the shaft bore and closed by
the clamping bolt. `Sk10Spec` in `hardware/linear_motion.py`
names each field descriptively and gives the vendor symbol in its comment (e.g. `shaft_h` [h],
`hole_pitch` [B]).

| Symbol | Value | Meaning |
|--------|-------|---------|
| d | 10 | Shaft diameter |
| h | 20 ±0.02 | Shaft center height above the mounting surface (**confirmed by user**) |
| E | 21 ±0.05 | Center to side (= W / 2) |
| W | 42 | Overall width (across the shaft) |
| L | 13.1 | Thickness along the shaft (**measured**; the vendor table says 14) |
| F | 37.5 | Overall height |
| G | 6 | Base flange thickness |
| P | 18 | Width of the upright body |
| B | 32.5 | Mounting-hole spacing: **measured** 2 mm from hole edge to the narrow edge, centered along the length (the table says 32). The base also has a ~1 mm chamfer on both narrow edges (hard to measure; modeled on the top edges, *assumed*) |
| S | 2 × Ø5.5 | Mounting holes, **M5** bolts |
| — | M4 | Clamping bolt |
| Mass | 24 g | Each |

## Derived: Y-axis height stack-up (from the shaft mounting surface)

| Level | Height | How |
|-------|--------|-----|
| Shaft center | 20 | SK10 h |
| SCS10UU base | 7 | 20 − 13 (block base sits 7 mm above the surface; it must clear the SK10 base and the bed) |
| SCS10UU top face | 33.5 | 7 + 26.5 (measured; 33.0 by the table) |
| Bed top (steel surface) | 14.8 | 5 adjuster gap + 9 panel + 0.8 steel (*design values, T3.7*) |
| Thickest media top | 29.8 | bed + 15 |
| Carriage bottom | ≥ 32.8 | media + 3 mm clearance |
| X beam bottom | **58** | carriage bottom + 24.8 (bottom V-wheels hang below the beam: 9.85 axis-to-face + 11.95 wheel radius + 3 margin) |
| X beam top | 98 | beam bottom + 40 |
| Y belt, top run (back of belt) | 33.5 | flush with the flat gantry bracket underside = SCS top (6 mm belt; the cap's 1.08 mm groove gives the 0.3 mm squeeze) |
| Y motor shaft / idler axle | ~26.8 | belt back − 0.38 (GT2 pitch line) − 6.37 (20T pitch radius) |
| Y endstop trigger screw | ~48.5 | on top of the gantry bracket, front-outboard corner |

So the gantry end brackets must lift the beam **~24.5 mm above the SCS top face**.
All of this is computed in `src/plotter_cad/params.py`; a design check (`params.design_checks()`) fails the build if the carriage
would hit 15 mm media.

**SCS10UU top face (measured by user):** two raised **10 mm flats**, one each side of the
shaft, running the full 35 mm length; between them a **17 mm wide recess, 1 mm deep**.
Chamfers on both edges of each flat (~0.75 mm each, *assumed* even split of the remaining
3 mm). The 4 × M5 holes (28 × 21 mm) sit in the middle of the flats (centers ±14 mm). The
gantry bracket bears on the two flats; a flat bracket underside clears the recess.
The 26.5 mm height is taken to the flats *(assumed)*.

## Motors, belts, pulleys, V-wheels

Design for the **common size** of each and adjust at assembly if a particular part
differs (user, T3.1). Values still *assumed* are marked.

### NEMA17 stepper

Motors on hand vary slightly; two common sizes measured:

| Motor | Body length | Shaft length (from the face) |
|-------|-------------|------------------------------|
| Typical (CAD default) | **39.2** | **22.6** |
| Short | 33.5 | 19 |

Design rules: mounts are face-mounted, so body length only matters for clearance; leave a
**48 mm** envelope (longest common NEMA17). Belt lines must sit within the **19 mm** shaft.

| Item | Value |
|------|-------|
| Body | 42.3 × 42.3 mm |
| Mounting holes | 4 × M3 on a 31 mm square, ~4.5 deep |
| Pilot boss | Ø22 × 2 mm |
| Shaft | Ø5, D-cut 0.5 mm *(assumed)* |
| Mass | ~280 g *(assumed)* |

### GT2 belt, pulley, idler

| Item | Value |
|------|-------|
| Belt | 2 mm pitch, **6 mm wide** (plenty on hand), 1.38 mm thick |
| Drive pulley | Common 20T, Ø5 bore, pitch Ø12.73; flange Ø16, length 16, hub 7 *(common values, assumed)* |
| Idler | Common toothed 20T, Ø5 bore, flange Ø18, width 8.5 *(common values, assumed)* |

### V-slot extrusion and V-wheels

| Item | Value |
|------|-------|
| Profile | 20 mm series V-slot (**4020 confirmed V-slot by user**); drawn as SVG sketches from a vendor drawing of the 2040: `src/plotter_cad/hardware/vslot_2020.svg`, `vslot_2040.svg` (D23). T-slot: lip **1.85** thick with a 45° chamfer (opening 9.9 at the face, **6.2** neck), cavity 12 wide, **6.1** deep to a 5.8 flat; bore **Ø4.2**; the 2040 has a closed octagonal cavity between its two cores. Bold = printed on the drawing; the rest scaled from it (±0.1, *assumed*). Section area 161 mm² (2020) / 296 mm² (2040) → ~0.44 / ~0.80 kg/m |
| V-wheel | **Ø24 × 10 mm** (user), POM on 2 × 625 bearings |
| Wheel axis to the extrusion face | **9.85** (standard 39.7 mm wheel spacing across 20 mm) *(assumed)* |
| Plain spacers | 6 mm *(assumed)* |
| Eccentric spacers | 2 used on the carriage's bottom wheels (D21). **Measured:** hex 10 across flats / 11.4 across corners, **7.8 long**; Ø5 bore (M5); Ø**7.1** boss (re-measured after the first print) **2.1 long** (into the plate) plus a ~0.5 mm boss on the wheel side; bore offset ~0.7 mm (±0.7 → 1.4 mm of adjustment; approximate). Plate face → wheel = **8.3 mm**: the top wheels must sit at the same distance |

### Endstop, servo, fasteners

| Item | Value |
|------|-------|
| Endstop | **Creality-type board** (from a Creality printer), measured with photos (`hardware/endstop.py`): board 20 wide × 19 long × **1.5 thick**, connector 10 wide × 7.2 long × 5.6 high (normal to the board), 2 mm of it past the rear edge (measured); a plug enters from the rear, so the CAD keeps a 15 mm × (10 + 2 × 2) mm × (5.6 + 2) mm space free behind it (`ENDSTOP.plug_len`, `plug_clearance`). **2 × M3 holes 15 mm apart** across the width at the rear (hole edges 1 mm from the sides, 1.5 mm from the rear edge). Micro switch **across the width at the front edge**: body 13 wide × 6.3 along the board × 5.3 high, protruding 1 mm past the front edge, ~2.5 mm right of center *(assumed)*. Lever: 3.8 wide × 0.3 thick metal strip hinged at the **left** end of the body's front face (board seen from above, connector at the rear), sweeping right: tip **5 mm** past the front edge at rest, **1.5 mm** fully pressed; length ~13.5 mm, hinge ~1.2 mm from the body end *(assumed)*. The trigger pushes it toward the board, along the board's length. Click point not measured (modeled at 75 % of the travel)  |
| Servo: **FeeTech FT90M** (chosen for the pen holder; metal gears, digital) | Body **23.2 × 12.1 × 25.5** (L × W × H; the height includes the round gear boss but not the output spline; **confirmed by the user's measurement**; boss **3.8**, so the body is 21.7), **13.5 g**, 1.9 kg·cm at 4.8 V, horn spline 20T / 3.95 mm (vendor listings). **Measured by the user:** tab span **32.5**, tabs **17** above the bottom of the body (to the underside of the tabs), mounting-hole spacing **28.5**, shaft center **5.9** from the end of the body. tab thickness **1.6**, mounting-hole Ø**1.8**. The servo comes with four horns (cross, two-sided, single-sided, disc); the **single-sided arm** is **17** from the shaft center to the tip, with **4 holes 2.5 apart, the last 1.9 from the tip**. Spline height above the boss and horn thickness not yet measured |
| Servo: FeeTech FS90 (spare) | Plastic gears, analog, ~23.2 × 12.5 × 22, 9 g; not used |
| M3 hex nut | ISO 4032: 5.5 across flats, 2.4 thick; pressed into printed slots (trap = AF + 0.1 (snug), thickness + 0.3, tune after a print); no heat-set inserts (D29) |
| Fasteners | ISO 4762 / ISO 4032 / ISO 7089 standard dimensions (`hardware/fasteners.py`) |

