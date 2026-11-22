"""Basic types shared across cadder. Depends on no other module of the package."""

from typing import Literal

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]

#: A handle: a 4×4 transformation matrix marking a position and orientation on a part.
Matrix = list[list[float]]

#: The coordinate frame a part is analyzed in: its output frame (the STL; for a print, the print
#: bed) or its installed frame (the assembly's, where loads are easiest to state).
Frame = Literal["output", "installed"]
