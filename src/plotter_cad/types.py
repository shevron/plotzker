"""Basic types shared across the package. Depends on no other module of ``plotter_cad``."""

from enum import Enum
from typing import Literal

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]

#: A handle: a 4×4 transformation matrix marking a position and orientation on a part.
Matrix = list[list[float]]

#: The coordinate frame a part is analyzed in: its print frame (the STL) or its installed frame.
Frame = Literal["print", "installed"]


class Side(Enum):
    """Which end of the gantry a part belongs to."""

    LEFT = "left"
    RIGHT = "right"
