"""The floating belt idler shared by the X and Y drives (STATUS.md T3.22, T3.23). Not printable.

A U-shaped slider carries the idler on an M5 axle. It has no rail: it is held only by an M3
tension screw that runs along the belt line at the axle's height through a *tower* (a plate with
two side walls, part of the left gantry bracket for X and of the idler mount for Y). The belt's pull
and the screw's are one line, so nothing twists the slider; the walls only keep it from rolling
while the screw is turned. The screw's head is on the tower plate's outer face; a captive nut at
the rear of the slider's wall pulls the slider toward the tower, and a blind tunnel in the wall
takes the screw's tip as the slider moves.

All geometry here is in the *tensioner frame*: x along the slide direction from the tower plate's
outer face, y along the axle with the belt line at y = 0, z as in the part that carries the tower.
:func:`slider_local` has the slider's rear face at x = 0; put it at ``rear_mid`` for mid-travel. The
parts that use it place it with a translation (X) or ``Placement`` (FEM) and a quarter turn (Y).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull

from plotter_cad.geometry import EPS, FN, FN_HOLE, teardrop_x, teardrop_y
from plotter_cad.loads import BeltLoads
from plotter_cad.nut_slot import nut_slot
from plotter_cad.params import TOL, FloatingIdler
from plotter_cad.part import DisplacementLimit, FemSpec, Force, LoadCase, Support
from plotter_cad.regions import Box, Cylinder, Placement

if TYPE_CHECKING:
    from pythonscad import Solid


def slider_local(t: FloatingIdler) -> Solid:
    """The slider with its rear face at x = 0 and its middle at y = 0."""
    w, zb, top = t.width, t.z_bottom, t.arm_top
    arms = []
    for sy in (-1, 1):
        y0 = -(t.gap_y / 2 + t.arm_t) if sy < 0 else t.gap_y / 2
        # the top front corner is a straight 45° line, tangent to the round end: printed upside
        # down it is no overhang that droops, so a slicer doesn't flip the part to avoid it
        arms.append(
            hull(
                cube([EPS, t.arm_t, top - zb]).translate([0, y0, zb]),
                cube([t.axle_x - t.arm_end_r, t.arm_t, EPS]).translate([0, y0, zb]),
                cube([EPS, t.arm_t, EPS]).translate([t.chamfer_x, y0, top - EPS]),
                cylinder(d=2 * t.arm_end_r, h=t.arm_t, fn=FN)
                .rotate([-90, 0, 0])
                .translate([t.axle_x, y0, t.axle_z]),
            )
        )
    web = cube([t.web_t, w, top - zb]).translate([0, -w / 2, zb])
    body = web | arms[0] | arms[1]
    # printed upside down (the top on the bed, +z down): the holes along y and x lie flat, so
    # their teardrops point to -z (print up); the nut pocket has a flat on that side (a 4.6 mm
    # bridge: a corner there would be a 30° overhang)
    axle_hole = (
        teardrop_y(TOL.bolt_hole_d(t.axle_m), w + 2)
        .rotate([180, 0, 0])
        .translate([t.axle_x, 0, t.axle_z])
    )
    axle_nut = (
        cylinder(d=TOL.nut_trap_ac(t.axle_m), h=TOL.nut_trap_h(t.axle_m) + 1, fn=6)
        .rotate([-90, 0, 0])
        .translate([t.axle_x, t.nut_y, t.axle_z])
    )
    screw_nut = nut_slot(t.screw_m, top - t.screw_z + 1, "x", "+z", t.nut_slot_extra).translate(
        [TOL.nut_wall + t.nut_t / 2, 0, t.screw_z]
    )
    # the screw's hole through the thrust wall and on into the blind tunnel for its tip
    tunnel = (
        teardrop_x(TOL.bolt_hole_d(t.screw_m), t.tunnel_end + 1)
        .rotate([180, 0, 0])
        .translate([(t.tunnel_end - 1) / 2, 0, t.screw_z])
    )
    return body - axle_hole - axle_nut - screw_nut - tunnel


def slider_for_print(t: FloatingIdler) -> Solid:
    """Print orientation: upside down, the slider's flat top on the bed. The layers then lie in
    the xy plane, parallel to both the belt's pull (x) and the axle's and the nut's tightening
    directions (y, x); the build direction is ``(0, 0, -1)`` in the tensioner frame."""
    return slider_local(t).rotate([180, 0, 0]).translate([0, 0, t.arm_top])


def tower(t: FloatingIdler) -> Solid:
    """The tower: a plate with the tension screw's hole and two side walls, standing on
    ``floor_z`` (sunk 1 mm into it). Pockets in the walls take the axle bolt's head (head side)
    and its tip (the other side) over the slider's travel."""
    half = t.tower_half
    z0 = t.floor_z - 1  # sunk into the floor: no sliver where the outer faces are flush
    h = t.tower_top - z0
    inner = t.width / 2 + t.wall_gap
    plate = cube([t.plate_t, 2 * half, h]).translate([0, -half, z0])
    walls = [cube([t.wall_len, half - inner, h]).translate([0, lo, z0]) for lo in (inner, -half)]
    # round, not a teardrop: a teardrop's apex was the highest stress in the plate (a 3.4 mm hole
    # prints flat enough lying on its side)
    hole = (
        cylinder(d=TOL.bolt_hole_d(t.screw_m), h=t.plate_t + 2, fn=FN_HOLE)
        .rotate([0, 90, 0])
        .translate([-1, 0, t.screw_z])
    )
    pockets = []
    for sign, (radius, depth) in ((t.head_side, t.head_pocket), (-t.head_side, t.tip_pocket)):
        x_lo, x_hi = t.sweep(radius)
        face = sign * inner
        y_lo, y_hi = (face - 1, face + depth) if sign > 0 else (face - depth, face + 1)
        pockets.append(
            cube([x_hi - x_lo, y_hi - y_lo, 2 * radius + 4]).translate(
                [x_lo, y_lo, t.axle_z - radius]
            )
        )
    return (plate | walls[0] | walls[1]) - hole - pockets[0] - pockets[1]


# --- FEM ------------------------------------------------------------------------------


@dataclass(frozen=True)
class FloatingRegions:
    """Load, support and limit regions of a floating idler, in the tensioner frame (slider at
    mid-travel)."""

    bore_load: Cylinder  #: the axle bore's wall pushed by the axle
    bore: Cylinder  #: the whole axle bore (the idler's position)
    nut_seat: Box  #: where the screw nut bears on the slider's thrust wall
    tunnel: Cylinder  #: the screw's hole and tunnel in the slider
    guide: Box  #: one outer face of the slider, standing for the tower's wall (roll)
    head_seat: Cylinder  #: the washer's seat on the tower plate's outer face
    tower_seat: Cylinder  #: the screw hole's wall in the tower plate


def regions(t: FloatingIdler) -> FloatingRegions:
    """The regions of idler ``t``."""
    r0 = t.rear_mid
    axle = (t.axle_rel, 0.0, t.axle_z)
    bore_r = TOL.bolt_hole_d(t.axle_m) / 2 + 0.3
    hole_r = TOL.bolt_hole_d(t.screw_m) / 2
    return FloatingRegions(
        bore_load=Cylinder(
            axle, (0, 1, 0), bore_r, t.width / 2, facing=(-1, 0, 0), facing_tol_deg=60
        ),
        bore=Cylinder(axle, (0, 1, 0), bore_r, t.width / 2),
        nut_seat=Box(
            (r0 + TOL.nut_wall - 0.3, -3, t.screw_z - 3),
            (r0 + TOL.nut_wall + 0.3, 3, t.screw_z + 3),
            facing=(1, 0, 0),
        ),
        tunnel=Cylinder(
            (r0 + t.tunnel_end / 2, 0, t.screw_z),
            (1, 0, 0),
            hole_r + 0.3,
            t.tunnel_end / 2,
            inner_radius=hole_r - 0.3,
        ),
        guide=Box(
            (r0, -t.width / 2 - 0.3, t.z_bottom),
            (r0 + t.web_t, -t.width / 2 + 0.3, t.arm_top),
            facing=(0, -1, 0),
        ),
        head_seat=Cylinder(
            (0, 0, t.screw_z),
            (1, 0, 0),
            t.washer_od / 2,
            0.3,
            inner_radius=hole_r,
            facing=(-1, 0, 0),
        ),
        tower_seat=Cylinder((t.plate_t / 2, 0, t.screw_z), (1, 0, 0), 2.6, t.plate_t / 2 + 0.5),
    )


def axes(place: Placement, flags: tuple[bool, bool, bool]) -> tuple[bool, bool, bool]:
    """Constraint flags (x, y, z of the tensioner frame) in the placed part's frame."""
    mapped = place.vector(tuple(1.0 if f else 0.0 for f in flags))
    return (abs(mapped[0]) > 0.5, abs(mapped[1]) > 0.5, abs(mapped[2]) > 0.5)


def head_load(t: FloatingIdler, place: Placement, pull: float) -> Force:
    """The screw's head pushing the tower with the idler's whole pull (the screw is in line)."""
    return Force(place.region(regions(t).head_seat), place.vector((pull, 0, 0)))


def tower_limits(
    t: FloatingIdler,
    place: Placement,
    prefix: str = "tower_seat",
    along_belt: float = 0.3,
    other: float = 0.1,
) -> tuple[DisplacementLimit, ...]:
    """Directional limits on the tower plate's screw hole: along the belt, across and vertical."""
    seat = place.region(regions(t).tower_seat)
    return (
        DisplacementLimit(f"{prefix}_along_belt", seat, along_belt, place.vector((1, 0, 0))),
        DisplacementLimit(f"{prefix}_sideways", seat, other, place.vector((0, 1, 0))),
        DisplacementLimit(f"{prefix}_vertical", seat, other, place.vector((0, 0, 1))),
    )


def slider_fem(t: FloatingIdler, place: Placement, belt: BeltLoads, source: str) -> FemSpec:
    """FEM spec of a floating slider: the belt pulls the axle bore; the screw nut's seat holds it
    along x, the screw in its hole and tunnel sideways and vertically, one face stands for a
    tower wall (roll, no load)."""
    r = regions(t)
    cases = []
    for name, run_n, sustained in (
        ("belt_preload", belt.preload_n, True),
        ("belt_peak", belt.peak_n, False),
    ):
        cases.append(
            LoadCase(
                name,
                f"Two belt runs of {run_n:g} N pull the idler along the belt; the tension screw, "
                "in line with the axle, holds the slider: no couple",
                (Force(place.region(r.bore_load), place.vector((2 * run_n, 0, 0)), bearing=True),),
                source,
                sustained=sustained,
            )
        )
    bore = place.region(r.bore)
    return FemSpec(
        load_cases=tuple(cases),
        supports=(
            Support(
                "screw_nut_seat",
                place.region(r.nut_seat),
                "Tension screw's nut seat: holds the slider along the belt",
                constrain=axes(place, (True, False, False)),
            ),
            Support(
                "screw_tunnel",
                place.region(r.tunnel),
                "The screw in the thrust wall's hole and the tunnel: holds sideways and vertically",
                constrain=axes(place, (False, True, True)),
            ),
            Support(
                "guide_wall",
                place.region(r.guide),
                "Tower wall beside the slider: stops the roll (no load)",
                constrain=axes(place, (False, True, False)),
            ),
        ),
        displacement_limits=(
            DisplacementLimit("idler_axle_along_belt", bore, 0.3, place.vector((1, 0, 0))),
            DisplacementLimit("idler_axle_sideways", bore, 0.1, place.vector((0, 1, 0))),
            DisplacementLimit("idler_axle_vertical", bore, 0.1, place.vector((0, 0, 1))),
        ),
    )


def mount_fem(
    t: FloatingIdler,
    place: Placement,
    belt: BeltLoads,
    source: str,
    supports: tuple[Support, ...],
) -> FemSpec:
    """FEM spec of a part that carries only the tower (the Y idler mount): the screw's head pushes
    the plate with the idler's whole pull; ``supports`` say how the part is held."""
    cases = []
    for name, run_n, sustained in (
        ("belt_preload", belt.preload_n, True),
        ("belt_peak", belt.peak_n, False),
    ):
        cases.append(
            LoadCase(
                name,
                f"Two belt runs of {run_n:g} N pull the idler along the belt; the tension screw's "
                "head pushes the tower plate with the same force, at the axle's height",
                (head_load(t, place, 2 * run_n),),
                source,
                sustained=sustained,
            )
        )
    return FemSpec(
        load_cases=tuple(cases), supports=supports, displacement_limits=tower_limits(t, place)
    )
