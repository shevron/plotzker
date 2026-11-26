"""Dimensions, position and design checks of the ZRIB mount under the baseboard (T3.7, D30)."""

from collections.abc import Iterator
from dataclasses import dataclass

from cadder.hardware import metric

from plotzker.legacy.zrib.board import ZRIB_SPEC
from plotzker.params import BASEBOARD, FRAME, WOOD_SCREW

# -----------------------------------------------------------------------------
# Two identical hangers (mirror images) screwed to the underside of the baseboard, one on
# each long side of the board; four posts carry the ZRIB with its components pointing down
# (heat sinks in free air), and two light straps under the legs guard the board's edges.
#
# Mount frame: u along the board's 110 mm (rear) edge = machine X, v toward the rear = machine
# Y, z up with 0 at the underside of the baseboard (the mount hangs at negative z).
#
#   side view along v (one hanger)            ▒▒ rail     ░ board  ▓ strap
#   baseboard ════════════════════════════
#   rail      ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒    ← wood screws at u = ±60 (outside the board)
#   post                ┃  ░░░░░░░░░░░  ┃            posts at the board's holes (u = ±50)
#   leg  ▒             board with parts ↓           ▒ leg
#        ▒                                        ▒
#   strap ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓


@dataclass(frozen=True)
class ZribMount:
    """ZRIB hangers and guard straps."""

    rail_thickness: float = 6  #: DESIGN (T3.7): hanger rail thickness (z)
    plate_thickness: float = 5  #: hanger rail thickness (v)
    post_dia: float = 9
    post_height: float = 5  #: board's solder side to the rail underside (room for the pin tails)
    leg_width: float = 8  #: along u (an M3 nut fits)
    leg_thickness: float = 9  #: along v (a nut slot reaches past the screw axis, with a wall)
    leg_gap: float = 11  #: board edge to the leg's inner face
    wood_screw_gap: float = 4  #: board edge to the screw center, along u
    wood_screw_v: float = 5  #: from the post row inward (v), clear of the strap for a driver
    boss_dia: float = 11.5  #: round boss that takes the screw head
    strap_thickness: float = 3
    strap_gap: float = 3  #: heat sink tops to the strap
    strap_screw_length: float = 12  #: M3

    @property
    def board_z(self) -> float:
        """Solder-side face of the board (negative z)."""
        return -(self.rail_thickness + self.post_height)

    @property
    def sink_bottom_z(self) -> float:
        """Lowest point of the heat sinks."""
        return self.board_z - ZRIB_SPEC.height

    @property
    def strap_top_z(self) -> float:
        """Top face of the strap."""
        return self.sink_bottom_z - self.strap_gap

    @property
    def strap_bottom_z(self) -> float:
        """Underside of the strap = the mount's total drop below the baseboard."""
        return self.strap_top_z - self.strap_thickness

    @property
    def leg_u(self) -> tuple[float, float]:
        """Leg extent along u (positive side)."""
        inner = ZRIB_SPEC.width / 2 + self.leg_gap
        return inner, inner + self.leg_width

    @property
    def wood_screw_u(self) -> float:
        """Wood screw position along u (positive side)."""
        return ZRIB_SPEC.width / 2 + self.wood_screw_gap

    @property
    def post_v(self) -> float:
        """Post row (negative-v side hanger): -hole pitch / 2."""
        return -ZRIB_SPEC.hole_pitch[1] / 2

    @property
    def plate_v(self) -> tuple[float, float]:
        """Plate extent along v (negative-v hanger): the outer face is flush with the posts'."""
        outer = self.post_v - self.post_dia / 2
        return outer, outer + self.plate_thickness

    @property
    def strap_screw_u(self) -> float:
        """Strap screw position along u (positive side): the leg's center."""
        return sum(self.leg_u) / 2

    @property
    def strap_screw_v(self) -> float:
        """Strap screw position along v (negative-v hanger): the leg's center."""
        return self.plate_v[0] + self.leg_thickness / 2

    @property
    def strap_nut_z(self) -> float:
        """Bottom of the strap screw's nut slot (the leg's end wall below it is 2 mm)."""
        return self.strap_top_z + 2


ZMOUNT = ZribMount()


@dataclass(frozen=True)
class ZribPosition:
    """Where the ZRIB mount sits under the baseboard."""

    #: centered between the first two runners, toward the right (its USB side faces +y)
    from_right: float = 180

    @property
    def center(self) -> tuple[float, float]:
        """ZRIB mount origin (the board's center) in the machine frame."""
        return FRAME.board_size[0] - self.from_right, (BASEBOARD.runner_y[0] + BASEBOARD.runner_y[1]) / 2

    @property
    def pilot_xy(self) -> tuple[tuple[float, float], ...]:
        """Pilot holes for the hangers' wood screws (mount frame u → x, v → y)."""
        center_x, center_y = self.center
        offset_u = ZMOUNT.wood_screw_u
        offset_v = abs(ZMOUNT.post_v + ZMOUNT.wood_screw_v)
        return tuple((center_x + su * offset_u, center_y + sv * offset_v) for sv in (-1, 1) for su in (-1, 1))


ZRIB_POSITION = ZribPosition()


def design_checks() -> Iterator[tuple[bool, str]]:
    """The ZRIB mount's design rules, as ``(ok, message)`` pairs."""
    yield (
        -ZMOUNT.strap_bottom_z <= 40,
        f"ZRIB mount hangs {-ZMOUNT.strap_bottom_z:g} mm below the baseboard (2040 on edge: 40)",
    )
    yield (
        ZMOUNT.wood_screw_u + ZMOUNT.boss_dia / 2 <= ZMOUNT.leg_u[0] - 1
        and ZMOUNT.wood_screw_u - WOOD_SCREW.head_dia / 2 >= ZRIB_SPEC.width / 2,
        "ZRIB mount wood screw boss hits the leg, or its head is not reachable beside the board",
    )
    yield (
        WOOD_SCREW.length - WOOD_SCREW.boss_thickness <= FRAME.board_size[2] - 2,
        "ZRIB mount wood screws would reach through the baseboard",
    )
    yield (
        WOOD_SCREW.boss_thickness > ZMOUNT.rail_thickness and -ZMOUNT.board_z - WOOD_SCREW.boss_thickness >= 1,
        "ZRIB mount boss hits the board",
    )
    center_x, center_y = ZRIB_POSITION.center
    half_v = abs(ZMOUNT.plate_v[0])
    yield (
        BASEBOARD.runner_pitch / 2 - BASEBOARD.runner_width / 2 - half_v >= 5
        and center_x + ZMOUNT.leg_u[1] <= FRAME.board_size[0],
        "The ZRIB mount does not fit between the runners or on the baseboard",
    )
    head_radius = metric(5).washer_outer_dia / 2 + 2  #: bed post bolt head and washer, plus room
    yield (
        not any(
            abs(x - center_x) < ZMOUNT.leg_u[1] + head_radius and abs(y - center_y) < half_v + head_radius
            for x, y in BASEBOARD.post_xy
        ),
        "A bed post bolt head hits the ZRIB mount",
    )
