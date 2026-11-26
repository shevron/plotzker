# Hardware reference dimensions

Vendor-part dimensions we design around. These values go into `cadder/src/cadder/hardware/` (generic vendor parts) or
`src/plotzker/hardware/` (the plotter's own), one frozen `*Spec` dataclass per part.
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
the clamping bolt. `Sk10Spec` in `cadder/hardware/linear_motion.py`
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
All of this is computed in `src/plotzker/params.py`; a design check (`params.design_checks()`) fails the build if the carriage
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
| Profile | 20 mm series V-slot (**4020 confirmed V-slot by user**); drawn as SVG sketches from a vendor drawing of the 2040: `cadder/src/cadder/hardware/vslot_2020.svg`, `vslot_2040.svg` (D23). T-slot: lip **1.85** thick with a 45° chamfer (opening 9.9 at the face, **6.2** neck), cavity 12 wide, **6.1** deep to a 5.8 flat; bore **Ø4.2**; the 2040 has a closed octagonal cavity between its two cores. Bold = printed on the drawing; the rest scaled from it (±0.1, *assumed*). Section area 161 mm² (2020) / 296 mm² (2040) → ~0.44 / ~0.80 kg/m |
| V-wheel | **Ø24 × 10 mm** (user), POM on 2 × 625 bearings |
| Wheel axis to the extrusion face | **9.85** (standard 39.7 mm wheel spacing across 20 mm) *(assumed)* |
| Plain spacers | 6 mm *(assumed)* |
| Eccentric spacers | 2 used on the carriage's bottom wheels (D21). **Measured:** hex 10 across flats / 11.4 across corners, **7.8 long**; Ø5 bore (M5); Ø**7.1** boss (re-measured after the first print) **2.1 long** (into the plate) plus a ~0.5 mm boss on the wheel side; bore offset ~0.7 mm (±0.7 → 1.4 mm of adjustment; approximate). Plate face → wheel = **8.3 mm**: the top wheels must sit at the same distance |

### Endstop, servo, fasteners

| Item | Value |
|------|-------|
| Endstop | **Creality-type board** (from a Creality printer), measured with photos (`hardware/endstop.py`): board 20 wide × **20.3 long** (caliper, T3.30; was recorded as 19) × **1.5 thick**, connector 10 wide × 7.2 long × 5.6 high (normal to the board), 2 mm of it past the rear edge (measured); a plug enters from the rear, so the CAD keeps a 13.5 mm (15 until T3.30) × (10 + 2 × 2) mm × (5.6 + 2) mm space free behind it (`ENDSTOP.plug_len`, `plug_clearance`). **2 × M3 holes 15 mm apart** across the width at the rear (hole edges 1 mm from the sides, 1.5 mm from the rear edge). Micro switch **across the width at the front edge**: body 13 wide × 6.3 along the board × 5.3 high, protruding 1 mm past the front edge, ~2.5 mm right of center *(assumed)*. Lever: 3.8 wide × 0.3 thick metal strip hinged at the **left** end of the body's front face (board seen from above, connector at the rear), sweeping right: tip **5 mm** past the front edge at rest, **1.5 mm** fully pressed; length ~13.5 mm, hinge ~1.2 mm from the body end *(assumed)*. The trigger pushes it toward the board, along the board's length. Click point not measured (modeled at 75 % of the travel). **Measured with the board resting on its underside (T3.14):** the flat PCB underside is 1.8 mm above the table, i.e. solder joints and pins stick out up to **1.8 mm** (uneven; tallest at the front-left, the switch's NC leg); the lever at rest spans 4.2–8.0 mm above the lowest solder tip, i.e. **2.4–6.2 above the flat PCB underside** (model: 2.25–6.05; it sags a little at the far end from its hinge); M3 head Ø5.34  |
| Servo: **FeeTech FT90M** (chosen for the pen holder; metal gears, digital) | Body **23.2 × 12.1 × 25.5** (L × W × H; the height includes the round gear boss but not the output spline; **confirmed by the user's measurement**; boss **3.8**, so the body is 21.7), **13.5 g**, 1.9 kg·cm at 4.8 V, horn spline 20T / 3.95 mm (vendor listings). **Measured by the user:** tab span **32.5**, tabs **17** above the bottom of the body (to the underside of the tabs), mounting-hole spacing **28.5**, shaft center **5.9** from the end of the body. tab thickness **1.6**, mounting-hole Ø**1.8**. The servo comes with four horns (cross, two-sided, single-sided, disc); the **single-sided arm** is **17** from the shaft center to the tip, with **4 holes 2.5 apart, the last 1.9 from the tip**. Spline height above the boss and horn thickness not yet measured |
| Servo: FeeTech FS90 (spare) | Plastic gears, analog, ~23.2 × 12.5 × 22, 9 g; not used |
| M3 hex nut | measured: 5.4 across flats, 2.25 thick; pressed into printed slots (hex-profile slot, `cadder.printing.nut_slot`: AF + 0.3 designed, thickness + 0.1; the print comes out ~0.1 narrower and ~0.1 thicker); no heat-set inserts (D29) |
| Fasteners | ISO 4762 / ISO 4032 / ISO 7089 standard dimensions (`cadder/hardware/fasteners.py`) |

### Power supply: Cheng Liang P360W24V

A generic "S-360" style enclosed supply, 24 V 15 A. There is no manufacturer drawing; the
values come from the user's caliper (**measured**) and from photos measured by the
former `photo-metrologist` agent (*photo ±x*, `photos/psu/report.md` and `features.json`, git-ignored).

**Frame:** origin at the corner where the terminal end, the **label wall** and the **bottom
face** meet. x runs across toward the **switch wall**, y from the terminal end to the fan end,
z from the bottom face to the fan face.
- **Bottom face** (z = 0): the face without the fan; it has the vent slots and mounting holes.
- **Fan face** (z = 50): the fan sits at the end away from the terminals.
- **Label wall** (x = 0): the side with the label, the output-adjust pot and the LED. It is on
  your left when you look at the terminals with the fan face up.
- **Switch wall** (x = 113): the side with the 115/230 V selector, behind the PE/N/L terminals.
- **Fan end** (y = 215): solid, with 5 case screws and no vents.

| Item | Value |
|------|-------|
| Size | **215 × 113 × 50** (measured); photo: 112.5 ±0.7 wide, 49.7 ±0.5 high |
| Mounting holes | All **M4** (measured) |
| Bottom face (z = 0) | **4 × M4 in a 150 × 50 rectangle**, centered: y **32 / 182**, x **31.5 / 81.5** (measured). Also, photo ±2, probably M3: a center hole at about (63.5, 120) and pressed-in hex nuts near the side edges at about y 8 and y 185–207 |
| Switch wall (x = 113) | **4 × M4**: y **32 / 182**, z **11.5 / 36.5** (measured: 25 apart, the top one 13.5 below the fan face) |
| Label wall (x = 0) | **2 × M4**: y **32 / 182**, z **10.5** (measured) |
| 115/230 V selector | On the switch wall: opening **15** (along y) × **8** (along z), bottom edge at z **11**, nearer edge **78 from the fan end**, so y 122–137 (measured; the photo shows which end, and that the 15 runs along the length). Must stay set to **230 V**; keep it covered or hidden from accidental flipping |
| Vents (keep open) | Bottom face: a row of 22 slots about 3 × 20 at 7.0 pitch along the label-wall edge (x 0–20, y 35–188.5, running round the bend), and a similar row along the switch-wall edge (extent not measured). Label wall near the terminal end: 3 tall slots at y about 7, 15 and 22 (z 9–35) and 2 short ones at y about 26 and 39 (z 9.5–17). The fan face: the fan, plus 2 × 5 slots near the terminal end. *photo ±1.5–2* |
| Terminal end: case | U-shaped case: the bottom plate and both walls run to y = 0. The fan-face cover stops **18.4 ±0.7** short (a stamped label lip, z 25.8–50), so the **top is open for y 0–18.4**. Inside width 110.5 ±0.8 (1.0 wall *assumed*). *photo* |
| Terminal block | 9-way barrier block: from the label wall, +V ×3, −V ×3, PE, N, L. Pitch **9.6 ±0.2** (probably the standard 9.5); screw centers at x 27.4 + 9.6·i (L at 104.2); block x 21.5–108.5, y 2.5–15.5, z 6–20 (±1.5). **The screws point toward the fan face (+z)**; the lugs go in sideways from the end, under a clear flap (front-bottom edge y 2.7, z 20.5). The screw heads stay inside the case; their tops are **~32 below the fan face** (z ~18; measured, matching the photo). They can be loose and stand proud, so leave several mm above them. The walls stick out **1.6** past the block front (measured; the photo said 2.5–4). The clear flap's top is about **26.5 below the fan face** (z ~23.5, measured). *photo except where marked* |
| Output-adjust pot / LED | Pot at about (13, 8.5, 18), adjusted from above; LED at (4, 17, 15). *photo ±3* |
| Wiring keep-out | The fork crimps reach x 22–110, z 5–20, up to **8.5** past the wall ends (y −8.5), and the wires continue from there. *photo ±2* |
| Mass | **770 g** with the C14 inlet and its wires (weighed) |

### C14 inlet (fused, switched; screw-mounted)

Measured by the user (T3.31). Model: `C14_INLET` in `src/plotzker/hardware/psu.py`.

| Item | Value |
|------|-------|
| Body (= panel cutout) | **47.3 × 27.3**; **16.7** deep behind the flange. At its bottom the side walls turn diagonal (the C14 socket's shape) and narrow to **15.2** |
| Push-on tabs | behind the body; length not measured (9 *assumed*) |
| Flange | elongated hexagon with rounded corners, **2.2** thick: **58.8** across the flats (the flat ends, along the body's long side) × **49.5** across the points (along its short side); flat ends 32 long *assumed* |
| Screw holes | **2 × Ø4**, **40 apart**, at the flange's points (across the body's short side): M3 screws |
| Fuse | fit a T3.15 A slow-blow (the PSU draws under 2 A at 230 V) |

### XT60H-F (female DC connector, PSU side)

Amass XT60H-F. Cross-sections **measured by the user** (caliper); lengths and the rim from
photos measured by the `photo-metrologist` (`photos/xt60/report.md`, git-ignored) and the Amass
drawing. Distances are from the mating face toward the wires; width = long side.

| Section | From the face | Width × height | Source |
|---------|---------------|----------------|--------|
| Front (mating) section; 45° chamfers 2.2 on one short side (2.0 flat between them) | 0 to **8.0** | **13.9 × 6.4** | measured; length from the test piece (7.2 proud of a 0.8 lip) |
| Collar (lettered); ~1.5 radius on its two corners on the chamfered side | 8.0 to **11.8** | **15.5 × 8.1** | measured (length too); the other two corners ~0.35 radius |
| Rim (flange) | 11.8 to 12.6 | **16.4 × 9.2** | Amass drawing |
| Black cap | 13.5 to **23.4** | 15.6 × 6.5 (±1) | *photo* |

Model: `XT60` in `src/plotzker/hardware/psu.py`.
