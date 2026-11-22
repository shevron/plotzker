#!/usr/bin/env python3
"""Apply the plotter's Marlin settings to a Marlin checkout (tested on tag 2.1.2.5).

Phase 2 first milestone: X axis only (docs/x-axis-bringup.md). Dual Y, servo and SD come later.
``X_MIN_ENDSTOP_INVERTING`` and ``INVERT_X_DIR`` are left at their defaults: set them from the
bench tests (guide section 5).

Usage: firmware/apply_config.py /path/to/Marlin [A4988|DRV8825]
"""

import argparse
import re
import sys
from pathlib import Path

#: Steps/mm of X for GT2, 20T, 1.8° with all MS jumpers fitted (1/16 resp. 1/32)
X_STEPS = {"A4988": 80, "DRV8825": 160}


def apply(path: Path, settings: dict[str, str]) -> None:
    """Set each ``#define NAME`` in ``path`` (the first one, commented out or not).

    The line's trailing comment is kept. Exits if a define is missing: that means the Marlin
    version differs from the tested one.
    """
    text = path.read_text()
    for name, value in settings.items():
        pattern = re.compile(
            rf"^(\s*)(?://\s*)?#define {name}\b[ \t]*([^\n/]*?)([ \t]*//[^\n]*)?$", re.MULTILINE
        )
        def replace(m: re.Match[str], name: str = name, value: str = value) -> str:
            return f"{m[1]}#define {name} {value}{m[3] or ''}".rstrip()

        text, n = pattern.subn(replace, text, count=1)
        if n != 1:
            sys.exit(f"{path.name}: no #define {name}")
    path.write_text(text)


def main() -> None:
    """Parse the arguments and edit the two configuration files."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("marlin", type=Path, help="path to the Marlin checkout")
    parser.add_argument("driver", nargs="?", default="A4988", choices=X_STEPS, help="X driver chip")
    args = parser.parse_args()

    apply(
        args.marlin / "Marlin/Configuration.h",
        {
            "MOTHERBOARD": "BOARD_ZRIB_V53",
            "EXTRUDERS": "0",  # heaters stay disabled (README 7.1)
            "TEMP_SENSOR_0": "0",
            "TEMP_SENSOR_BED": "0",
            "X_DRIVER_TYPE": args.driver,
            # EXTRUDERS 0: three axes only (a fourth value fails Marlin's sanity checks)
            "DEFAULT_AXIS_STEPS_PER_UNIT": f"{{ {X_STEPS[args.driver]}, 80, 400 }}",
            "DEFAULT_MAX_FEEDRATE": "{ 100, 100, 5 }",
            "DEFAULT_MAX_ACCELERATION": "{ 500, 500, 100 }",
            "HOMING_FEEDRATE_MM_M": "{ (20*60), (20*60), (4*60) }",
            "X_BED_SIZE": "410",
            "Y_BED_SIZE": "540",
            "X_MAX_POS": "X_BED_SIZE",
            "Y_MAX_POS": "Y_BED_SIZE",
        },
    )
    apply(
        args.marlin / "Marlin/Configuration_adv.h",
        {"PINS_DEBUGGING": "", "AXIS_RELATIVE_MODES": "{ false, false, false }"},
    )
    print(f"Applied. Build: cd {args.marlin} && pio run -e mega2560")


if __name__ == "__main__":
    main()
