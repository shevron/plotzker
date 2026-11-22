# X-axis bring-up guide (Phase 2, first milestone)

**Goal:** the printed gantry and X carriage are assembled, the X motor and X− endstop are
wired to the ZRIB and the 24 V supply, Marlin is flashed, and `G28 X` moves the carriage to
the endstop, stops, and sets X = 0.

**Not needed yet:** Y axis (shafts, SK10s, Y belts, Y motors and endstops), baseboard, bed,
pen holder, servo, loom, ZRIB hangers. This guide is the first slice of T2.1–T2.5
(`STATUS.md` T2.7). Pin facts: [`controller.md`](controller.md); part sizes:
[`hardware.md`](hardware.md).

> **Rules for the whole session.** (1) Never plug or unplug a motor, driver or endstop with
> 24 V on: it kills drivers. (2) Wire mains only with the plug out of the wall. (3) Keep a
> hand near the PSU switch (or the plug) whenever the carriage moves. (4) Heaters stay
> disconnected and disabled (README §7.1 rule 4).

---

## 1. What you need

### Print (default profile: PETG, 0.6 mm nozzle, 0.3 mm layers; STLs in `stl/`)

| Part | Qty | Notes |
|------|-----|-------|
| `gantry_end_bracket_left` / `_right` | 1 + 1 | Left has the idler tower and shelf |
| `x_carriage` | 1 | Front face down, no supports |
| `x_motor_mount` | 1 | The STL is already the right-hand (mirrored) part |
| `x_endstop_mount` | 1 | Foot that carries the endstop board |
| `x_idler_slider` | 1 | Prints upside down (top on the bed) |
| `belt_clamp` | 2 | The X belt's two ends (Y needs 4 more later) |

Do **not** print `x_idler_mount.stl`: it is left over from the old design. If you change the
CAD, run `make stl` first. Print the carriage first and test-fit the nuts, wheels and beam
before printing the rest (the follow-ups in `STATUS.md` T3.3, T3.22 list what to check).

### Hardware

| Item | Qty |
|------|-----|
| 4020 V-slot beam, 520 mm, M5 tapped in the end bores | 1 |
| SCS10UU blocks | 4 |
| M5×20 socket head | 16 (12 into the blocks, 4 into the beam ends) |
| M5×25 socket head | 4 for the bolts that pass through the motor-mount and endstop-mount feet, plus 1 for the idler axle |
| M5×42 socket head + washer + nyloc nut | 4 each (V-wheel axles) |
| V-wheels Ø24 × 10 (625 bearings) | 4 |
| Eccentric spacers (10 mm hex) | 2 (bottom wheels) |
| M5 nut | 1 (idler axle) |
| NEMA17 motor | 1 |
| 20T GT2 pulley, Ø5 bore | 1 |
| 20T GT2 toothed idler, Ø5 bore | 1 |
| GT2 belt, 6 mm | about 1.3 m (cut to length at assembly) |
| M3×10 (motor) | 4 |
| M3×14 + M3 nut (belt clamps) | 4 + 4 |
| M3×25 + M3 nut + large M3 washer (idler tension screw) | 1 each |
| M3×12 + 2 M3 nuts (X endstop trigger on the carriage) | 1 + 2 |
| M3×6 + M3 nut (endstop board) | 2 + 2 |
| Creality-type endstop board with its cable | 1 |

The bolt counts follow the assembly model (`assemblies/gantry.py`); verify when you build.

### Electronics and tools

ZRIB v5.8, one StepStick driver (A4988 on hand), the 24 V PSU, mains cable and plug,
USB-B cable (data, not charge-only), multimeter, small ceramic or plastic screwdriver (Vref
pot), hex keys, ruler or calipers, a flat table, a non-slip mat.

---

## 2. Assemble the mechanics

1. **Carriage.** Press M3 nuts into their pockets (see the part's docstring). Mount the 4
   V-wheels with M5×42 bolts from the front (washer and head sit in the counterbores,
   nyloc nut on the wheel side). The bottom pair goes on the eccentric spacers (the Ø7.1
   boss goes into the plate). Leave the bottom wheels loose and the eccentrics open.
2. **Carriage on the beam, then the brackets.** Slide the carriage onto the beam **before**
   the brackets go on (they close the ends). Then bolt each bracket to a beam end with 2 ×
   M5×20 into the end bores.
3. **Preload.** Turn the eccentrics until the carriage rolls with a light, even drag and no
   rattle; tighten the bottom nuts. Too tight makes the motor stall; too loose rattles.
4. **Blocks.** Set the beam and brackets on 4 SCS10UU blocks on the table (no shafts needed
   for this test; the blocks sit on their base flanges on the non-slip mat) and bolt each
   bracket to its 2 blocks with M5×20.
5. **Motor and endstop feet.** Place the motor mount's foot on the right bracket and the
   endstop mount's foot on the left bracket, under the rear block's bolt heads, and fit
   the M5×25 bolts that pass through them (the foot clamps under the head): 2 per side in the
   assembly model (some part docstrings still say 4; check against the parts).
6. **Motor.** Fit the NEMA17 with 4 × M3×10 (shaft toward the beam). Put the 20T pulley on
   the shaft, **hub toward the motor**, belt line level with the idler, set screw on the
   shaft's flat. Tighten it after the belt is on.
7. **Idler.** Idler between the two arms of the slider with the M5×25 axle (head on the
   rear arm, nut pressed into the front arm). Slide the slider into the tower on the left
   bracket and thread the M3×25 tension screw (with its large washer) from the tower's outer
   face into the slider's captive nut. Back the screw out so the slider is at its belt-side
   end of travel for now.
8. **Belt.** Run the belt from one carriage clamp, around the motor pulley and the idler,
   and back to the other clamp (teeth toward the pulleys; the clamp caps sit on top of the
   belt, ridges in the tooth gaps). Leave about 40 mm beyond each clamp, then tighten the 4
   M3×14. Tension with the screw until the belt deflects about 2 mm under a finger at
   mid-run: snug, not guitar-string tight. Then tighten the pulley's set screw.
9. **Endstop.** Fix the board to the endstop mount's foot with 2 × M3×6 (nuts in the
   underside pocket; the solder side faces the recess). On the carriage, screw the M3×12
   trigger into the rear block's left end through its captive nut, with a lock nut outside,
   so its head presses the lever as the carriage nears the left end. Set its depth in the endstop test
   (§5).
10. **Free-move check, power off.** Push the carriage by hand over the whole beam: smooth,
    no binding, the belt doesn't rub, the pulley and idler turn freely, the carriage doesn't
    hit the brackets or the endstop plug at either end.

---

## 3. Electronics

```
 wall ─► [fuse/switch] ─► PSU 24 V ─ V+ / V− ─► ZRIB DC input (+ / −)
                                                 ├─ X-MOT  ◄── NEMA17 (4 wires)
                                                 ├─ X−     ◄── endstop (S, G)
 Mac ──── USB-B ───────────────────────────────► ZRIB USB
```

1. **PSU.** Plug out of the wall. Wire L, N and earth to the PSU's mains terminals with a
   proper cable; cover the terminals; check the earth pin is connected to the PSU's earth
   terminal. This is the only dangerous step: if you are not sure, stop and ask. Set the
   PSU's 115/230 V switch (if any) for your mains.
2. **Drivers.** Read the chip markings (note them for T2.1). Put the driver in the **X**
   socket only, the right way round (match the board's silkscreen: reversed drivers
   die). Leave the other sockets empty for now. Check the MS1–MS3 jumpers under the X
   socket: all three fitted gives 1/16 on an A4988 (80 steps/mm) and 1/32 on a DRV8825 (160
   steps/mm).
3. **Vref.** Our X driver is a red A4988 clone (pins `EN MS1 MS2 MS3 RST SLP STP DIR`); the chip
   is under the heatsink and the sense resistors are not readable, so start at **Vref = 0.4 V**:
   about 1.0 A with 0.05 Ω sense resistors, 0.7 A with 0.068 Ω, 0.5 A with 0.1 Ω (A4988:
   I = Vref / (8 × R)), all safe for a NEMA17. With the motor unplugged and the board powered,
   measure between the pot's metal screw and GND and adjust slowly with a ceramic or plastic
   screwdriver. Raise it only if the motor skips. (For a DRV8825: I = Vref / (5 × 0.1 Ω).)
4. **Motor.** Plug it into X-MOT with power off. Find the two coil pairs with the
   multimeter if the plug isn't keyed (low resistance within a pair, open between pairs).
5. **Endstop.** Plug it into the **X−** header. **Check the pin order first:** the board's
   switch must connect signal (S) and ground (G); with the carriage away from it, find the
   pins that have continuity at rest (normally closed) or when pressed (normally open).
   Those two go to S and G of the X− header. A plug in the wrong order can put 5 V across
   the switch: confirm with the multimeter, not by trying.
6. **PSU to board.** Connect V+ to +, V− to −, polarity checked twice; the board does not
   survive reversed polarity. Strain-relieve the wires.
7. **Power-up order:** USB only first (Marlin talks, nothing moves; see §4), then the 24 V
   with the carriage resting mid-beam.

---

## 4. Firmware (Marlin 2.1.x)

**Tools and build (once):**

```bash
uv tool install platformio
git clone --branch 2.1.2.5 https://github.com/MarlinFirmware/Marlin.git ~/Marlin
uv run firmware/apply_config.py ~/Marlin A4988      # or DRV8825: the chip in the X socket
```

`firmware/apply_config.py` sets everything in [`firmware/README.md`](../firmware/README.md)
(board `BOARD_ZRIB_V53`, no extruders or temperature sensors, driver type, steps/mm, gentle
speeds and acceleration, slow homing, 410 × 540 travel, `PINS_DEBUGGING`). It leaves two
settings for the bench: `X_MIN_ENDSTOP_INVERTING` (from the `M119` test) and `INVERT_X_DIR`
(from the direction test); edit them in `~/Marlin/Marlin/Configuration.h`. On macOS the board
shows up as `/dev/cu.usbserial-*` (CP210x); install the Silicon Labs driver only if it doesn't.

```bash
cd ~/Marlin
pio run -e mega2560                  # compiles
pio run -e mega2560 -t upload        # board on USB, 24 V off
pio device monitor -b 250000         # Marlin's default baud rate
```

If the upload fails: wrong or busy port, charge-only cable, or the Mac needs the driver.
The build was checked with tag 2.1.2.5 (it compiles); it has not been flashed to the board yet.

---

## 5. Tests

Type each command in the serial monitor. `M112` is the emergency stop; the PSU switch is
the real one.

| # | Do | Expect |
|---|----|--------|
| 1 | USB only, `M115` | Firmware info |
| 2 | `M119` | All endstops `open` (or per your wiring) |
| 3 | Power on 24 V, `M17` | Motor holds the shaft (hard to turn by hand), driver warm not hot |
| 4 | `M211 S0` (soft limits off, since nothing is homed), `G91`, `G1 X10 F1200` | Carriage moves 10 mm **toward the motor (right)** |
| 5 | `G1 X100 F3000`, measure; then `G1 X-110 F3000`, `G90`, `M211 S1` | Moves 100 mm (±1); if not, `M92 X<80 × 100/measured>`, `M500` |
| 6 | Endstop and homing: see below | |

**Direction.** If step 4 moved the carriage left, set `INVERT_X_DIR true`, rebuild and
reflash (or power off and flip the motor plug).

**Endstop (motor off with `M18`).**

1. Press the lever by hand and run `M119`: expect `x_min: TRIGGERED`, released: `open`. If
   it is the other way round, flip the endstop's logic in `Configuration.h` and reflash.
2. Push the carriage slowly to the left by hand while repeating `M119`: it must trigger
   from the trigger screw's head with at least 3 mm of carriage travel left before the
   carriage hits anything. Adjust the screw's depth and tighten its lock nut.

**Homing.** Park the carriage in the middle (mid-beam is about X = 200). `G28 X` at the
slow homing speed: the carriage goes left, clicks, backs off a few mm, approaches slowly,
stops. `M114` then shows X:0.00. Hand on the switch; if anything is wrong, cut the power.

Finish with repeatability: `G1 X200 F3000`, `G28 X`, ten times; mark the carriage against a
fixed point each time. Then `G1 X400 F3000` (soft limit now active), `G28 X`, and `M211`
to confirm the limits are on.

**Success:** the X axis is smooth over the whole travel, the carriage homes onto the endstop
at least 10 times in a row at the same spot (±0.1 mm), and it stays within the soft limits.

---

## 6. Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Monitor shows nothing | Wrong baud rate (250000), wrong port, charge-only cable |
| Motor buzzes, doesn't turn | Coils not paired on the plug; Vref too low; driver in backwards |
| Motor stalls or skips | Vref too low; wheels preloaded too tight; belt too tight; acceleration too high; belt rubbing |
| Wrong direction | `INVERT_X_DIR` (§5, "Direction") |
| Homing goes away from the endstop | Direction wrong (as above); `X_HOME_DIR` not −1 |
| `x_min` always TRIGGERED | Wrong logic setting; pin order; cable not on X− |
| Board resets when the motor moves | Loose 24 V connection; reversed polarity is a different, serious failure: stop |
| Driver very hot | Vref too high; no heat sink or airflow |

---

## 7. Report back

So that T2.1–T2.3 can be closed from this session, write down:

- the PSU label, the driver chip markings and sense resistors, the MS jumper state, the Marlin tag;
- what worked and what didn't (with photos of any failure);
- the measured steps/mm, the trip point (mm of carriage travel from click to the bracket), and the repeatability;
- which endstop logic setting was right, and the X− header's pin labels.
