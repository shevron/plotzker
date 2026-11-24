"""Creality-type mechanical endstop board (user's, from a Creality printer). Dimensions in mm.

Measured by the user (T3.5, with photos): board 20 wide × 20.3 long × 1.5 thick (length
re-measured with the caliper in T3.30; T3.5 had 19); two M3 mounting holes 15 apart,
across the width at the rear (connector) end, hole edges 1 mm from the sides and 1.5 mm
from the rear edge. The connector, on the component side at
the rear, is 10 wide × 7.2 long × 5.6 high (normal to the board), 2 mm of it past the rear
edge; a plug slides onto it from the rear, so the space behind it must stay free.

The micro switch lies across the board's width at the front edge, its body protruding
1 mm past the edge: 13 wide × 6.3 along the board × 5.3 above it. A thin metal lever
(3.8 wide × 0.3 thick) is hinged at the *left* end of the body's front face (board seen
from above, connector at the rear) and sweeps diagonally to the right: at rest its tip
is 5 mm past the board's front edge, fully pressed 1.5 mm. A trigger pushing the lever
toward the board (along the board's length) presses it.

Model frame (all functions here): origin at the front edge of the board's bottom face,
centered across the width; ``u`` = right, ``v`` = toward the front, ``w`` = up (from the
board's bottom face; the components are on the +w side). ``u × v = w``.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cadder.handles import place_in_frame
from pythonscad import cube, cylinder

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class EndstopSpec:
    """Endstop board, switch and lever dimensions."""

    #: length (front-rear, measured T3.30) × width × thickness
    pcb: tuple[float, float, float] = (20.3, 20, 1.5)
    hole_pitch: float = 15  #: across the width (measured)
    hole_m: float = 3
    hole_d: float = 3.0  #: = 20 - 15 - 2 × 1 mm edge distance
    hole_from_rear: float = 1.5  #: edge of the hole to the rear edge (measured)
    body: tuple[float, float, float] = (13, 6.3, 5.3)  #: across × along the board × above it
    body_overhang: float = 1.0  #: body front face past the board's front edge (measured)
    body_u: float = 2.5  #: body center, right of the board center. ASSUMED (from the photos)
    lever_len: float = 13.5  #: hinge to tip. ASSUMED (from the photos)
    lever_w: float = 3.8  #: across the board's normal (measured)
    lever_t: float = 0.3
    pivot_inset: float = 1.2  #: hinge from the body's left end. ASSUMED (from the photos)
    rest_protrusion: float = 5.0  #: lever tip past the board's front edge at rest (measured)
    pressed_protrusion: float = 1.5  #: ... fully pressed (measured)
    #: DESIGN: the trigger presses this far in from the lever tip (raises the right-hand Y
    #: board enough that its plug space clears the belt)
    contact_inset: float = 4.0
    #: DESIGN: share of the lever's travel at the contact point that the trigger uses at the
    #: end of travel. The switch's click point is ASSUMED to lie below this.
    press_fraction: float = 0.75
    connector: tuple[float, float, float] = (10, 7.2, 5.6)  #: width × length × height (measured)
    connector_overhang: float = 2  #: connector past the rear edge (measured)
    #: DESIGN: free space behind the connector for a plug and the bend of its wires, and the
    #: clearance around the plug's sides and top
    plug_len: float = 13.5  #: 15 until T3.30; shortened so the X idler tower keeps its walls
    plug_clearance: float = 2

    @property
    def thickness(self) -> float:
        """Board underside to the top of the tallest part (body or connector)."""
        return self.pcb[2] + max(self.body[2], self.connector[2])

    @property
    def plug_keepout_v(self) -> float:
        """Rear end of the plug keep-out, behind the front edge (negative)."""
        return -(self.pcb[0] + self.connector_overhang + self.plug_len)

    @property
    def hole_v(self) -> float:
        """Hole center line, along the board (negative = behind the front edge)."""
        return -(self.pcb[0] - self.hole_from_rear - self.hole_d / 2)

    @property
    def pivot_u(self) -> float:
        """Lever hinge, across the board."""
        return self.body_u - self.body[0] / 2 + self.pivot_inset

    @property
    def lever_z(self) -> float:
        """Lever center above the board's bottom face (centered on the body). ASSUMED"""
        return self.pcb[2] + self.body[2] / 2

    @property
    def contact_s(self) -> float:
        """Distance of the trigger contact point from the hinge, along the lever."""
        return self.lever_len - self.contact_inset

    def lever_angle(self, protrusion: float) -> float:
        """Lever angle (radians) from the board's width axis for a tip ``protrusion``."""
        return math.asin((protrusion - self.body_overhang) / self.lever_len)

    @property
    def contact_u(self) -> float:
        """Trigger contact across the board, with the lever at rest."""
        return self.pivot_u + self.contact_s * math.cos(self.lever_angle(self.rest_protrusion))

    @property
    def contact_rest_v(self) -> float:
        """Lever surface at the contact point, past the board's front edge, at rest."""
        return self.body_overhang + self.contact_s * math.sin(
            self.lever_angle(self.rest_protrusion)
        )

    @property
    def contact_travel(self) -> float:
        """Lever travel at the contact point, rest to fully pressed."""
        return self.contact_s * (
            math.sin(self.lever_angle(self.rest_protrusion))
            - math.sin(self.lever_angle(self.pressed_protrusion))
        )

    @property
    def trigger_v(self) -> float:
        """Trigger tip past the board's front edge at the end of travel."""
        return self.contact_rest_v - self.press_fraction * self.contact_travel


ENDSTOP = EndstopSpec()


def endstop(pressed: bool = False) -> Solid:
    """Endstop board in the model frame (see the module docstring); lever at rest or pressed."""
    e = ENDSTOP
    length, width, t = e.pcb
    holes = [
        cylinder(d=e.hole_d, h=t + 2, fn=16).translate([su * e.hole_pitch / 2, e.hole_v, -1])
        for su in (-1, 1)
    ]
    pcb = (cube([width, length, t]).translate([-width / 2, -length, 0]) - holes).color("Black")
    body_w, body_h, body_d = e.body
    body = (
        cube([body_w, body_h, body_d])
        .translate([e.body_u - body_w / 2, e.body_overhang - body_h, t])
        .color("#222")
    )
    conn_w, conn_l, conn_h = e.connector
    connector = (
        cube([conn_w, conn_l, conn_h])
        .translate([-conn_w / 2, -length - e.connector_overhang, t])
        .color("White")
    )
    protrusion = e.pressed_protrusion if pressed else e.rest_protrusion
    lever = (
        cube([e.lever_len, e.lever_t, e.lever_w])
        .translate([0, -e.lever_t / 2, -e.lever_w / 2])
        .rotate([0, 0, math.degrees(e.lever_angle(protrusion))])
        .translate([e.pivot_u, e.body_overhang, e.lever_z])
        .color("Silver")
    )
    return pcb | body | connector | lever


def endstop_keepout() -> Solid:
    """Space that must stay free behind the connector for a plug, in the model frame."""
    e = ENDSTOP
    width = e.connector[0] + 2 * e.plug_clearance
    rear_face = -(e.pcb[0] + e.connector_overhang)
    return cube(
        [width, rear_face - e.plug_keepout_v, e.pcb[2] + e.connector[2] + e.plug_clearance]
    ).translate([-width / 2, e.plug_keepout_v, 0])


def endstop_placed(
    origin: Sequence[float],
    u: Sequence[float],
    v: Sequence[float],
    w: Sequence[float],
    pressed: bool = False,
) -> Solid:
    """The board with its model-frame axes ``u``, ``v``, ``w`` (right-handed) along the given
    directions of the destination frame and its origin at ``origin``."""
    return place_in_frame(endstop(pressed), origin, u, v, w)
