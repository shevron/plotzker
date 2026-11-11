# Controller: Zonestar ZRIB v5.8

Notes on the controller board, how we plan to use it, and how to verify the pin map
before building. Based on photos of the board (2026-11-10) and Marlin's
`pins_ZRIB_V53.h` (bugfix-2.1.x).

## What the board has (from photos)

| Feature | Observed on v5.8 | Notes |
|---------|------------------|-------|
| MCU | Atmel **ATmega2560-16AU**, 16 MHz crystal | Same MCU as RAMPS/MKS Base |
| USB | USB-B, Silabs USB-serial chip (CP210x) | Appears as a serial port; needs the CP210x driver on macOS only if not auto-detected |
| Stepper drivers | **6 socketed StepStick-format drivers**: X, Y, Z, E0, E1, E2 | Removable, so they can be swapped/upgraded (e.g. TMC2208/2209 in standalone mode for quieter motion) |
| Driver types | Mix: 3 white boards, 3 red boards | Probably A4988 clones, possibly mixed types. **Check chip markings under the heatsinks.** Both Y motors must use the same driver type |
| Motor connectors | E2-MOT, X-MOT, Y-MOT, E0-MOT (top); E1-MOT, ZMOT1/ZMOT2 (right) | ZMOT1/ZMOT2 + jumper = two Z motors on one driver (printer dual-Z) |
| Endstops | X−, Y−, Z− (top/right, 3-pin); X+, Y+, Z+ (S/G/V row near EXP1) | 6 inputs, min and max per axis |
| Expansion headers | XS1 (2×4), XS2 (2×3), a 2×3 header with pin-1 marker left of the MCU, AUX (5-pin JST, right edge) | See pin map and to-verify below |
| LCD | EXP1 + EXP2 (10-pin boxed) | Standard RepRap 12864 layout per Marlin pin file |
| SD | microSD (TF) slot with 74HC4050 level shifter | Can plot from SD card without a PC |
| 5 V supply | **Switching (buck) regulator** (large inductor) + small linear regulator; USB/VREG power-select jumper | Buck regulator should be good for a small servo; confirm under load |
| Power / outputs | Screw terminals: power in (12–24 V), heated bed, hotend(s), AUX-12V; JST fan and thermistor (E0TEMP, BTEMP) connectors | Heater outputs unused for heating; MOSFET outputs could drive a solenoid |

## Marlin board definition

Marlin has three ZRIB definitions: `BOARD_ZRIB_V20`, `BOARD_ZRIB_V52`, `BOARD_ZRIB_V53`.
There is none for v5.8. **`BOARD_ZRIB_V53` is the best match:**

- It defines **6 stepper drivers including E2** (V5.2 supports only 2 E steppers). This
  matches the 6 sockets on v5.8.
- It defines an **XS1 2×4 header** (`5V GND NC 47 / 42 43 44 45`), matching the 2×4 XS1 on v5.8.
- Same min/max endstop layout, EXP1/EXP2 layout, and MKS-Base heritage.

Key pins from `pins_ZRIB_V53.h` (to be verified on the v5.8, see below):

| Function | Arduino pin | Notes |
|----------|-------------|-------|
| X step/dir/en | 54 / 55 / 38 | |
| Y step/dir/en | 60 / 61 / 56 | |
| Z step/dir/en | 46 / 48 / 62 | |
| E0 step/dir/en | 26 / 28 / 24 | **Y2 motor** (see allocation) |
| E1 step/dir/en | 36 / 34 / 30 | spare |
| E2 step/dir/en | 4 / 5 / 22 | spare |
| X−, X+ | 3, 2 | |
| Y−, Y+ | 14, 15 | |
| Z−, Z+ | 18, 19 | |
| SERVO0, SERVO1 | 65 (A11), 66 (A12) | 2×3 "Servos / XS3" header: `signal GND 5V` × 2. Probably the **XS2** header on v5.8, to verify |
| Heater 0 / Heater 1 / Bed | 10 / 7 / 8 | MOSFET outputs |
| Fan 0 / Fan 1 | 9 / 6 | MOSFET outputs |
| EXP1 pins 3 / 4 | 17 (RX2) / 16 (TX2) | Hardware **Serial2**: a candidate port for the TFT35-E3 |
| SD card CS | 53 | |

## Planned allocation for the plotter

| Function | Driver / pin | Marlin setting |
|----------|-------------|----------------|
| X motor | X driver | — |
| Y motor (left) | Y driver | — |
| Y2 motor (right) | **E0 driver** (first free E driver when `EXTRUDERS 0`) | `Y_DUAL_STEPPER_DRIVERS`, Y2 driver type set |
| X home | X− | `X_HOME_DIR -1` |
| Y home (left) | Y− | `Y_DUAL_ENDSTOPS` |
| Y2 home (right) | Y+ input (pin 15) used as the Y2 endstop | `Y2_USE_ENDSTOP _YMAX_` |
| Pen lift servo | SERVO0 (pin 65) | `NUM_SERVOS 1`, `M280 P0 S<angle>` |
| Optional stepper Z (pen experiments) | Z driver + Z− endstop | |
| Optional solenoid (pen experiments) | Fan 1 (D6) or Heater 1 (D7) MOSFET output | `M42` / custom G-code; flyback diode |
| Future pen changer | E1, E2 drivers; X+, Z+ inputs; XS1 pins | spare |
| Heaters | **disabled**: `EXTRUDERS 0`, `TEMP_SENSOR_* 0`; nothing connected | |

## Things to verify on the bench (before relying on the pin map)

Marlin's `M43` pin-debugging command (`PINS_DEBUGGING`) makes this quick and safe:

1. **Driver chips:** read the markings (A4988 / DRV8825 / other) on all 6 drivers.
   Put two **identical** drivers in the Y and E0 sockets. Set Vref for the motors (A4988
   and DRV8825 use different formulas).
2. **Microstepping jumpers:** check the jumpers under each driver socket (MS1–MS3);
   use 1/16 for A4988 (1/32 for DRV8825).
3. **Endstops:** with Marlin flashed, `M43 W` (watch pins) while pressing each switch, and
   confirm X−=3, X+=2, Y−=14, Y+=15, Z−=18, Z+=19.
4. **Steppers:** jog each axis with only one motor attached; confirm each socket drives
   the expected axis (especially E0 → Y2).
5. **Servo header:** confirm which 2×3 header is the servo port: XS2, or the marked
   header left of the MCU (this one is more likely ICSP). With the board on USB, measure
   5 V/GND on the header, then `M280 P0 S90` and watch a servo or a scope/LED on the signal pin.
6. **5 V capacity:** run the servo against a stall briefly and check that the board doesn't
   brown out. If it resets, power the servo from a separate 5 V buck converter (common GND).
7. **AUX connector (right edge, 5-pin):** identify its pins with a multimeter. It may be
   a serial port, which would be convenient for the TFT35-E3.
8. **PSU voltage:** read the label (12 V or 24 V). The board accepts 12–24 V.

## TFT35-E3 connection options

- **Serial (touch mode, preferred):** TFT's RS232 header (5V, GND, TX, RX) → a hardware
  UART on the ZRIB. Candidates: EXP1 pins 3/4 (Serial2, D17 RX2 / D16 TX2) with a custom
  cable, or the AUX connector if it turns out to be serial. Marlin: `SERIAL_PORT_2 2`.
- **12864 emulation mode:** EXP1/EXP2 ribbon cables, Marlin
  `REPRAP_DISCOUNT_FULL_GRAPHIC_SMART_CONTROLLER`. Simpler wiring, but you get only the
  classic menu UI.
- Both together is possible (EXP for the encoder-style UI, serial for touch mode) as long
  as Serial2 isn't also used by EXP1 for the LCD. Decide during bring-up.
