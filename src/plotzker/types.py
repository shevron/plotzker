"""Basic types of the plotter. Depends on no other module of ``plotzker``."""

from enum import Enum


class Side(Enum):
    """Which end of the gantry a part belongs to."""

    LEFT = "left"
    RIGHT = "right"
