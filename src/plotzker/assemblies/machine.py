"""The whole machine (T3.7): drilled baseboard with runners, shafts and bed, gantry, Y and X
drives, carriage and the v1 pen holder, with the ZRIB under the board.

Machine frame (``params``). Used for the overall fit check (travel, clearances, 15 mm media
under the head) and the renders. Not printable.
"""

from typing import TYPE_CHECKING

from pythonscad import translate

from plotzker.assemblies import baseboard, loom
from plotzker.assemblies.pen_holder import pen_holder_assembly
from plotzker.assemblies.skeleton import carriage_x_at, gantry_y_at, moving_parts

if TYPE_CHECKING:
    from pythonscad import Solid


def pen_holder_at(gantry_pos: float = 0.5, carriage_pos: float = 0.5, pen_up: bool = True) -> list[Solid]:
    """The pen holder on the carriage at the given travel fractions (0..1)."""
    return [
        translate(item, [carriage_x_at(carriage_pos), gantry_y_at(gantry_pos), 0])
        for item in pen_holder_assembly(pen_up)
    ]


def machine_assembly(gantry_pos: float = 0.5, carriage_pos: float = 0.5, pen_up: bool = True) -> list[Solid]:
    """Everything, with the gantry and carriage at the given travel fractions (0..1)."""
    return [
        *baseboard.fixed_assembly(),
        *loom.rails(),
        *moving_parts(gantry_pos, carriage_pos),
        *loom.y_loom(gantry_y_at(gantry_pos)),
        *pen_holder_at(gantry_pos, carriage_pos, pen_up),
    ]


def machine() -> list[Solid]:
    """The machine at mid-travel, pen up (render)."""
    return machine_assembly()
