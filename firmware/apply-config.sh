#!/usr/bin/env bash
# Apply the plotter's Marlin settings to a Marlin checkout (tested on tag 2.1.2.5).
# Usage: firmware/apply-config.sh /path/to/Marlin [A4988|DRV8825]
# Phase 2 first milestone: X axis only (docs/x-axis-bringup.md). Dual Y, servo and SD come later.
# X_MIN_ENDSTOP_INVERTING and INVERT_X_DIR are left at their defaults: set them from the
# bench tests (guide §5).
set -euo pipefail
exec python3 - "${1:?path to the Marlin checkout}" "${2:-A4988}" <<'PY'
import re, sys
from pathlib import Path

root, drv = Path(sys.argv[1]), sys.argv[2]
steps = {"A4988": 80, "DRV8825": 160}[drv]  # all MS jumpers fitted: 1/16 resp. 1/32

def apply(path: Path, settings: dict[str, str]) -> None:
    text = path.read_text()
    for name, value in settings.items():
        # the first `#define NAME ...` line, commented out or not; keeps its trailing comment
        pat = re.compile(rf"^(\s*)(?://\s*)?#define {name}\b[ \t]*([^\n/]*?)([ \t]*//[^\n]*)?$", re.M)
        text, n = pat.subn(lambda m: f"{m[1]}#define {name} {value}{m[3] or ''}", text, count=1)
        if n != 1:
            sys.exit(f"{path.name}: no #define {name}")
    path.write_text(text)

apply(root / "Marlin/Configuration.h", {
    "MOTHERBOARD": "BOARD_ZRIB_V53",
    "EXTRUDERS": "0",
    "TEMP_SENSOR_0": "0",
    "TEMP_SENSOR_BED": "0",
    "X_DRIVER_TYPE": drv,
    "DEFAULT_AXIS_STEPS_PER_UNIT": f"{{ {steps}, 80, 400 }}",
    "DEFAULT_MAX_FEEDRATE": "{ 100, 100, 5 }",
    "DEFAULT_MAX_ACCELERATION": "{ 500, 500, 100 }",
    "HOMING_FEEDRATE_MM_M": "{ (20*60), (20*60), (4*60) }",
    "X_BED_SIZE": "410",
    "Y_BED_SIZE": "540",
    "X_MAX_POS": "X_BED_SIZE",
    "Y_MAX_POS": "Y_BED_SIZE",
})
apply(root / "Marlin/Configuration_adv.h", {
    "PINS_DEBUGGING": "",
    "AXIS_RELATIVE_MODES": "{ false, false, false }",  # EXTRUDERS 0: three axes only
})
print("Applied. Build: cd", root, "&& pio run -e mega2560")
PY
