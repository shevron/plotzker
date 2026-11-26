"""Apply the plotter's Marlin settings to a Marlin checkout (tested on tag 2.1.2.5).

For the Creality V4.2.2 board (GD32F303, HR4988 drivers). Phase 2 first milestone: X axis only
(docs/x-axis-bringup.md). Dual Y, servo and SD come later. ``X_MIN_ENDSTOP_INVERTING`` and
``INVERT_X_DIR`` are left at their defaults: set them from the bench tests (guide section 5).

Usage: ``uv run firmware/apply_config.py [MARLIN_DIR]``; the default is ``vendor/Marlin`` in this
project (git-ignored).
"""

import re
from pathlib import Path
from typing import Annotated

import typer

#: Where the Marlin checkout lives (git-ignored)
MARLIN_DIR = Path(__file__).resolve().parents[1] / "vendor/Marlin"
#: Marlin has no HR4988 type; it is driven like an A4988
DRIVER = "A4988"
#: PlatformIO environment; the GD32F303 runs the STM32F103RE build
BUILD_ENV = "STM32F103RE_creality"


def apply(path: Path, settings: dict[str, str]) -> None:
    """Set each ``#define NAME`` in ``path`` (the first one, commented out or not).

    The line's trailing comment is kept. Fails if a define is missing: that means the Marlin
    version differs from the tested one.
    """
    text = path.read_text()
    for name, value in settings.items():
        pattern = re.compile(rf"^(\s*)(?://\s*)?#define {name}\b[ \t]*([^\n/]*?)([ \t]*//[^\n]*)?$", re.MULTILINE)

        def replace(m: re.Match[str], name: str = name, value: str = value) -> str:
            return f"{m[1]}#define {name} {value}{m[3] or ''}".rstrip()

        text, count = pattern.subn(replace, text, count=1)
        if count != 1:
            typer.secho(f"{path.name}: no #define {name}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
    path.write_text(text)


def main(
    marlin: Annotated[Path, typer.Argument(help="Path to the Marlin checkout.", exists=True)] = MARLIN_DIR,
) -> None:
    """Apply the plotter's Marlin settings (X-axis bring-up) to a Marlin checkout."""
    apply(
        marlin / "Marlin/Configuration.h",
        {
            "MOTHERBOARD": "BOARD_CREALITY_V422",
            "SERIAL_PORT": "1",  # the CH340 USB port
            "BAUDRATE": "115200",
            "EXTRUDERS": "0",  # heaters stay disabled (README 7.1)
            "TEMP_SENSOR_0": "0",
            "TEMP_SENSOR_BED": "0",
            "X_DRIVER_TYPE": DRIVER,
            "Y_DRIVER_TYPE": DRIVER,
            "Z_DRIVER_TYPE": DRIVER,
            "FAN_SOFT_PWM": "",  # required by this board's pin definition
            "EEPROM_SETTINGS": "",  # M500 saves to the board's I2C EEPROM
            # EXTRUDERS 0: three axes only (a fourth value fails Marlin's sanity checks)
            "DEFAULT_AXIS_STEPS_PER_UNIT": "{ 80, 80, 400 }",
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
        marlin / "Marlin/Configuration_adv.h",
        {"PINS_DEBUGGING": "", "AXIS_RELATIVE_MODES": "{ false, false, false }"},
    )
    typer.secho(f"Applied. Build: pio run -d {marlin} -e {BUILD_ENV}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    typer.run(main)
