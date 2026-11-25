# Controller: Creality V4.2.2

The plotter's controller (STATUS D41). Facts from the user's photo of the board (2026-11-25) and
Marlin 2.1.2.5's `pins_CREALITY_V422.h`. The pin map is not yet verified on the bench.

## What the board has

| Feature | Observed | Notes |
|---------|----------|-------|
| MCU | GigaDevice **GD32F303** | STM32F103 compatible; the `STM32F103RE_creality` build runs on it (flashed 2026-11-26) |
| USB | micro-USB, CH340 serial chip | 115200 baud |
| Drivers | 4 soldered (X, Y, Z, E), sticker on the SD slot **`H8`** | HR4988 per Marlin's key (chips under heatsinks, unread); `X_DRIVER_TYPE A4988`; 1/16 microstepping |
| Current setting | trim pots RP1 (X), RP2 (Y), RP3 (Z), RP4 (E) | sense resistors `R150` (0.15 Ω): I = Vref / 1.2 |
| Motor supply | 100 µF **35 V** capacitors, TVS diodes, blade fuse | input marked 24 V DC |
| Endstops | X−, Y−, Z−: **2-pin** (user) | Ender 3 cable: 2 pins at the board; at the endstop module wire **V** and **S** (G empty): normally closed |
| `BL_T` header | `G V IN G OUT` | `OUT` = SERVO0 (PB0), `IN` = probe input (PB1) |
| Other | microSD (flashing and files), I²C EEPROM, 10-pin LCD connector | heater, fan and thermistor connectors stay empty |

Board outline, holes and height: not measured yet (T3.32).

## Pins (`BOARD_CREALITY_V422`)

| Function | Pins |
|----------|------|
| X step / dir | PC2 / PB9 |
| Y step / dir | PB8 / PB7 |
| Z step / dir | PB6 / PB5 |
| E0 step / dir | PB4 / PB3 |
| Enable (all drivers share it) | PC3 |
| X−, Y−, Z− | PA5, PA6, PA7 |
| SERVO0 / probe input | PB0 / PB1 |
| Heater, bed, fan | PA1, PA2, PA0 |
| UART3 TX / RX (LCD connector) | PB10 / PB11 |

## Planned allocation

| Function | Driver / pin | Marlin setting |
|----------|-------------|----------------|
| X motor | X driver | — |
| Y motor (left) | Y driver | — |
| Y2 motor (right) | E0 driver | `Y_DUAL_STEPPER_DRIVERS` |
| X home | X− | `X_HOME_DIR -1` |
| Y home (left) | Y− | `Y_DUAL_ENDSTOPS` |
| Y2 home (right) | Z− input | `Y2_USE_ENDSTOP` on Z min (check at T2.2) |
| Pen lift servo | `BL_T` OUT | `NUM_SERVOS 1`, `M280 P0 S<angle>` |
| Optional stepper Z | Z driver; endstop on `BL_T` IN | |
| Optional solenoid | fan or heater MOSFET | `M42`; flyback diode |
| Heaters | **disabled**: `EXTRUDERS 0`, `TEMP_SENSOR_* 0`; nothing connected | |

All motors share one enable line: they hold and release together. There are no spare drivers
for a pen changer.

## Bench results (X axis, 2026-11-26)

- Flashed from microSD; X motor on the X driver holds and moves; direction right
  (`INVERT_X_DIR false`).
- X driver Vref **0.88 V** (0.73 A).
- X endstop on X−: reads `open` released, `TRIGGERED` pressed once wired to V and S on the
  module (`X_MIN_ENDSTOP_INVERTING false`). With the cable's wires as delivered it read inverted.
- `G28 X` homes.

## To verify on the bench

1. Factory Vref of the four drivers; set X as in the [bring-up guide](x-axis-bringup.md) §3.
2. Which edge connector is X−, Y−, Z−; endstop logic (`M119`, `M43 W`).
3. Each driver drives the expected motor (E0 as Y2).
4. Servo on `BL_T`: 5 V holds with the servo stalled; if the board resets, use a separate 5 V
   buck converter (common GND).
5. PSU: ✅ Cheng Liang P360W24V, 24 V, 15 A max, 215 × 113 × 50 mm (user).

## TFT35-E3 (optional)

Touch mode talks serial: UART3 on the LCD connector (`SERIAL_PORT_2 3`), through an adapter
cable. The connector's 5 V and GND positions are to be checked first.

## Set aside: Zonestar ZRIB v5.8

Primary until 2026-11-25; the full notes (pin map, allocation, drivers) are in this file at git tag
`pre-creality-board`. **Do not power it from 24 V:**

- After smoke at a power-up, the electrolytic capacitor under the **E1** socket, marked
  **100 25V VT** (100 µF, 25 V), has burn marks. 25 V leaves almost no margin at 24 V.
- The white E1 driver above it ran very hot with no motor: treat it as faulty.
- The X socket's `RST`/`SLP` read about 1.7 V, so the driver stayed disabled (cause not found).
- The first motor had its coils on pins 1–3 and 2–4: a likely contributor.

Its board is 95 × 110 mm, 22 mm to the heat sink tops, with 4 × Ø3 holes 80 × 100 mm apart; the
CAD's controller mount still uses these (T3.32).
