# Firmware

Marlin 2.1.x for the Creality V4.2.2 (`BOARD_CREALITY_V422`, GD32F303). We keep a script that
applies our settings to a stock Marlin checkout instead of a copy of Marlin's files.
Marlin is GPL-3.0: any Marlin file or diff added here stays under that license (README §8).

**Tested:** tag `2.1.2.5` with `apply_config.py`: `pio run -e STM32F103RE_creality` compiles
(flash 14.9 %, RAM 7.2 %). Flashed from microSD to the GD32F303 board; `M115` answers, the X motor moves and `G28 X` homes
(2026-11-26). Repeatability, travel and steps/mm not measured yet (T2.7).

Run from the project folder; `vendor/` is git-ignored.

```bash
uv tool install platformio                     # once
git clone --branch 2.1.2.5 https://github.com/MarlinFirmware/Marlin.git vendor/Marlin
uv run firmware/apply_config.py                # configures vendor/Marlin
pio run -d vendor/Marlin -e STM32F103RE_creality
```

Flash from a FAT32 microSD card: copy `vendor/Marlin/.pio/build/STM32F103RE_creality/firmware-….bin` to its top
folder and power the board on (guide [`x-axis-bringup.md`](../docs/x-axis-bringup.md) §4). Then
`pio device monitor -b 115200`, and `M502`, `M500`.

## What the script sets (X-axis bring-up)

| Setting | Value | Why |
|---------|-------|-----|
| `MOTHERBOARD` | `BOARD_CREALITY_V422` | the board |
| `SERIAL_PORT`, `BAUDRATE` | `1`, `115200` | the CH340 USB port |
| `EXTRUDERS`, `TEMP_SENSOR_0`, `TEMP_SENSOR_BED` | `0` | heaters stay disabled (README §7.1) |
| `X_`, `Y_`, `Z_DRIVER_TYPE` | `A4988` | HR4988 (sticker `H8`); Marlin has no HR4988 type |
| `FAN_SOFT_PWM` | on | required by the board's pin definition |
| `EEPROM_SETTINGS` | on | `M500` saves to the board's EEPROM |
| `DEFAULT_AXIS_STEPS_PER_UNIT` | `{ 80, 80, 400 }` | GT2, 20T, 1/16 |
| `DEFAULT_MAX_FEEDRATE` / `_ACCELERATION` | `{ 100, 100, 5 }` mm/s / `{ 500, 500, 100 }` mm/s² | gentle |
| `HOMING_FEEDRATE_MM_M` | 20 mm/s on X and Y | slow homing |
| `X_BED_SIZE`, `Y_BED_SIZE` | 410, 540 | travel (`X_MAX_POS`, `Y_MAX_POS` follow) |
| `PINS_DEBUGGING` | on | `M43` |
| `AXIS_RELATIVE_MODES` | 3 elements | required when `EXTRUDERS` is 0 |

With `EXTRUDERS 0` Marlin wants **3-element** axis arrays (no E value); a 4th one fails the build.

**Bench results (2026-11-26):** `X_MIN_ENDSTOP_INVERTING false` and `INVERT_X_DIR false` (both
Marlin defaults) are right, with the endstop wired normally closed (module pins V and S,
[`docs/controller.md`](../docs/controller.md)).
**Later (T2.2, T2.4):** `Y_DUAL_STEPPER_DRIVERS`, `Y_DUAL_ENDSTOPS`, `NUM_SERVOS`, SD card, Y driver types.
