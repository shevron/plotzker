# Firmware

Marlin 2.1.x for the ZRIB v5.8 (`BOARD_ZRIB_V53`). We keep a script that applies our settings
to a stock Marlin checkout instead of a copy of Marlin's files.
Marlin is GPL-3.0: any Marlin file or diff added here stays under that license (README §8).

**Tested:** tag `2.1.2.5` with `apply_config.py`, A4988 and DRV8825 variants: `pio run -e mega2560`
compiles (flash 18.8 %, RAM 27.6 %). Not yet flashed to the board (T2.7).

```bash
uv tool install platformio                     # once
git clone --branch 2.1.2.5 https://github.com/MarlinFirmware/Marlin.git ~/Marlin
uv run firmware/apply_config.py ~/Marlin A4988        # or DRV8825
cd ~/Marlin && pio run -e mega2560 -t upload   # board on USB, 24 V off
pio device monitor -b 250000
```

## What the script sets (X-axis bring-up)

| Setting | Value | Why |
|---------|-------|-----|
| `MOTHERBOARD` | `BOARD_ZRIB_V53` | closest match (`docs/controller.md`) |
| `EXTRUDERS`, `TEMP_SENSOR_0`, `TEMP_SENSOR_BED` | `0` | heaters stay disabled (README §7.1) |
| `X_DRIVER_TYPE` | `A4988` or `DRV8825` | the chip in the X socket |
| `DEFAULT_AXIS_STEPS_PER_UNIT` | `{ 80, 80, 400 }` (X = 160 for DRV8825 on 1/32) | GT2, 20T |
| `DEFAULT_MAX_FEEDRATE` / `_ACCELERATION` | `{ 100, 100, 5 }` mm/s / `{ 500, 500, 100 }` mm/s² | gentle |
| `HOMING_FEEDRATE_MM_M` | 20 mm/s on X and Y | slow homing |
| `X_BED_SIZE`, `Y_BED_SIZE` | 410, 540 | travel (`X_MAX_POS`, `Y_MAX_POS` follow) |
| `PINS_DEBUGGING` | on | `M43` |
| `AXIS_RELATIVE_MODES` | 3 elements | required when `EXTRUDERS` is 0 |

With `EXTRUDERS 0` Marlin wants **3-element** axis arrays (no E value); a 4th one fails the build.

**Left for the bench:** `X_MIN_ENDSTOP_INVERTING` and `INVERT_X_DIR` (edit `Configuration.h` by hand
after the tests in `docs/x-axis-bringup.md` §5, then record the result here).
**Later (T2.2, T2.4):** `Y_DUAL_STEPPER_DRIVERS`, `Y_DUAL_ENDSTOPS`, `NUM_SERVOS`, SD card, Y driver types.
