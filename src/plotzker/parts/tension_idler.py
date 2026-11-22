"""Generic belt-tensioning idler (prototype, not yet used in the machine). Print ×1 of each.

Purpose: holds a toothed GT2 idler on an M5 axle supported at **both** ends, and tensions
the belt. Two separately printed parts: a **rail** (base plate, dovetail ridge,
end block) and a **slider** (U-shaped: two arms joined by a rear wall and a plate with a
dovetail channel underneath). A captive M3 nut in the slider's rear wall and an M3 screw
through the rail's end block pull the slider toward the block, away from the belt.

  top view                                  side view (arms cut away at the axle)
  ┌───────────────────────────┐            ┌─┐   ◯ idler / axle (M5)
  │ ▓ block │ web ═arm════◯ ← open front    │▓│ ┌─┴──────────┐ ← slider plate
  │ ▓  M3 ──┼─nut  ═arm════  (belt leaves)  │▓│ └────────────┘
  └───────────────────────────┘             └─┴─────────────────  rail + dovetail

Frame (installed, both parts together): rail on z = 0; x = slide direction, belt leaves toward +x;
x = 0 is the end block's outer face (screw head); idler axle along y, y = 0 on the middle;
z up. The pair is shown with the slider at mid-travel; ``tension_idler_rail()`` and
``tension_idler_slider()`` are the print orientations (each flat on z = 0).

Hardware: toothed idler (``IDLER``); 1 × M5×25 ISO 4762 (axle, head on the -y arm) + 1 × M5
nut (pressed into the +y arm's outside); 1 × M3 nut (pressed in from the top of the rear
wall) + 1 × M3×``screw_len`` ISO 4762 (tension screw, from the block's outside);
4 × M3 ISO 4762 through the rail plate to mount it.
Print: PETG; 0.2 mm; 4 perimeters; 40 % infill; rail flat on its plate; slider lying on its
back (rear wall on the bed); no supports and no bridges (the dovetail runs vertically; the nut
slot's ceiling spans only the nut's width).
Dovetail clearance ``slide_gap`` (0.2 mm per side): tune after a test print.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cadder.geometry import EPS, FN, FN_HOLE, teardrop_x, teardrop_y
from cadder.handles import handle, set_handles
from cadder.hardware import metric
from cadder.printing import nut_slot
from cadder.regions import Box, Cylinder, Placement
from pythonscad import cube, cylinder, hull, linear_extrude, polygon, union

from plotzker.loads import BeltLoads
from plotzker.params import TENSION_IDLER, TOL, TensionIdler
from plotzker.part import DisplacementLimit, FemSpec, Force, LoadCase, Moment, Support

if TYPE_CHECKING:
    from pythonscad import Solid

T = TENSION_IDLER
#: Slider rear face at mid-travel
SLIDER_X0 = T.block_t + T.stop_gap + T.travel / 2


def slider_x0(t: TensionIdler = T) -> float:
    """Slider rear face at mid-travel, from the end block's outer face (x = 0)."""
    return t.block_t + t.stop_gap + t.travel / 2


def _yz_extrude(points: list[tuple[float, float]], x0: float, length: float) -> Solid:
    """A polygon given in (y, z), extruded along +x from ``x0``."""
    return (
        linear_extrude(polygon([list(p) for p in points]), height=length)
        .rotate([90, 0, 90])
        .translate([x0, 0, 0])
    )


def ridge(t: TensionIdler, x0: float, length: float) -> Solid:
    """Dovetail ridge on the rail surface at ``z = t.rail_t``: narrow at its base, 45° flanks."""
    z0 = t.rail_t - EPS
    n, h = t.ridge_neck / 2, t.ridge_h
    pts = [(-n, z0), (n, z0), (n + h, z0 + h + EPS), (-n - h, z0 + h + EPS)]
    return _yz_extrude(pts, x0, length)


def _cavity(t: TensionIdler, length: float) -> Solid:
    """The slider's dovetail channel: the ridge grown by the sliding clearance."""
    g = t.slide_gap
    z_bottom = t.slider_z0 - 1
    k = g * math.sqrt(2)  # horizontal offset of a 45° flank for a perpendicular gap g
    n, h = t.ridge_neck / 2, t.ridge_h

    def half(z: float) -> float:
        return n + (z - t.rail_t) + k

    z_top = t.rail_t + h + g
    pts = [
        (-half(z_bottom), z_bottom),
        (half(z_bottom), z_bottom),
        (half(z_top), z_top),
        (-half(z_top), z_top),
    ]
    return _yz_extrude(pts, -1, length + 2)


def end_block(t: TensionIdler = T, z0: float = 0) -> Solid:
    """The rail's screw end block (outer face at x = 0), from ``z0`` up, with the screw hole."""
    top = t.screw_z + metric(t.screw_m).head_d / 2 + TOL.min_wall
    block = cube([t.block_t, t.block_w, top - z0]).translate([0, -t.block_w / 2, z0])
    hole = teardrop_x(TOL.bolt_hole_d(t.screw_m), 2 * t.block_t).translate([0, 0, t.screw_z])
    return block - hole


def rail(t: TensionIdler = T) -> Solid:
    """The generic fixed part: base plate with mounting holes, dovetail ridge, end block."""
    plate = cube([t.rail_len, t.rail_w, t.rail_t]).translate([0, -t.rail_w / 2, 0])
    m = t.mount_m
    hole_y = t.rail_w / 2 - t.mount_margin / 2
    hole_x = TOL.cbore_d(m) / 2 + TOL.min_wall
    holes = []
    for sx in (hole_x, t.rail_len - hole_x):
        for sy in (-1, 1):
            holes.append(
                cylinder(d=TOL.bolt_hole_d(m), h=t.rail_t + 2, fn=FN_HOLE).translate(
                    [sx, sy * hole_y, -1]
                )
            )
            cbore_h = metric(m).head_h + 0.5
            holes.append(
                cylinder(d=TOL.cbore_d(m), h=cbore_h + 1, fn=FN_HOLE).translate(
                    [sx, sy * hole_y, t.rail_t - cbore_h]
                )
            )
    return (plate | ridge(t, 0, t.rail_len) | end_block(t)) - union(*holes)


def slider(t: TensionIdler = T) -> Solid:
    """The moving part: U-shaped carrier with the axle holes and the tension nut pocket.

    Frame: the rail's (x = 0 at the end block's outer face), slider at mid-travel.
    """
    x0 = slider_x0(t)
    length, w = t.length, t.width
    z0, zt = t.slider_z0, t.slider_z0 + t.plate_t
    arm_top = t.axle_z + t.arm_end_r
    plate = cube([t.plate_len, w, t.plate_t]).translate([0, -w / 2, z0])
    # beyond the plate each arm's underside rises at 45°, clear of what is cut into the arm, so
    # the round ends print without support; the line starts on the plate's top face, or below it
    # on the plate's front face when the plate is short
    r = t.arm_end_r
    top = arm_top + 1
    arms = []
    for sy in (-1, 1):
        y0 = sy * (t.gap_y / 2 + t.arm_t) if sy < 0 else t.gap_y / 2
        xp = t.arm_chamfer_x(nut_side=sy == -t.head_side)
        x_start = min(xp, t.plate_len)
        z_start = zt - (xp - x_start)
        low = min(z_start, zt) - 1
        above_chamfer = polygon(
            [
                [-1, low],
                [x_start, low],
                [x_start, z_start],
                [xp + top, zt + top],
                [xp + top, top],
                [-1, top],
            ]
        )
        clip = linear_extrude(above_chamfer, height=t.arm_t).rotate([90, 0, 0])  # xz profile
        profile = hull(
            cube([EPS, t.arm_t, arm_top - zt + EPS]).translate([0, y0, zt - EPS]),
            cube([x_start, t.arm_t, EPS]).translate([0, y0, zt - EPS]),
            cube([EPS, t.arm_t, EPS]).translate([x_start - EPS, y0, z_start]),
            cylinder(d=2 * r, h=t.arm_t, fn=FN)
            .rotate([-90, 0, 0])
            .translate([t.axle_x, y0, t.axle_z]),
        )
        arms.append(profile & clip.translate([0, y0 + t.arm_t, 0]))
    web = cube([t.web_t, w, arm_top - zt + EPS]).translate([0, -w / 2, zt - EPS])
    body = (plate | union(*arms) | web).translate([x0, 0, 0])

    # printed on its back (+x up): the axle hole's teardrop and the nut pocket's corner point +x
    axle_hole = (
        teardrop_y(TOL.bolt_hole_d(t.axle_m), w + 2)
        .rotate([0, 90, 0])
        .translate([x0 + t.axle_x, 0, t.axle_z])
    )
    axle_nut = (
        cylinder(d=TOL.nut_trap_ac(t.axle_m), h=TOL.nut_trap_h(t.axle_m) + 1, fn=6)
        .rotate([-90, 0, 0])
        .translate([x0 + t.axle_x, t.nut_y, t.axle_z])
    )
    nut_t = TOL.nut_trap_h(t.screw_m) + t.nut_slot_extra
    screw_nut = nut_slot(
        t.screw_m, arm_top - t.screw_z + 1, "x", "+z", t.nut_slot_extra, tol=TOL
    ).translate([x0 + TOL.nut_wall + nut_t / 2, 0, t.screw_z])
    screw_hole = (
        cylinder(d=TOL.bolt_hole_d(t.screw_m), h=2 * length, fn=FN_HOLE)
        .rotate([0, 90, 0])
        .translate([x0 - length / 2, 0, t.screw_z])
    )
    cut = _cavity(t, t.plate_len).translate([x0, 0, 0])
    return body - cut - axle_hole - axle_nut - screw_nut - screw_hole


def slider_for_print(t: TensionIdler = T) -> Solid:
    """The slider in print orientation: lying on its back (the rear wall on the bed), so the
    dovetail runs vertically and its roof is a vertical wall, not a bridge."""
    top = t.axle_z + t.arm_end_r - t.slider_z0
    return (
        slider(t)
        .translate([-slider_x0(t), 0, -t.slider_z0])
        .rotate([0, -90, 0])
        .translate([top, 0, 0])
    )


def tension_idler_installed() -> Solid:
    """Rail and slider assembled (slider at mid-travel), with handles for the hardware.

    Handles (z = hardware axis, pointing out of the head): ``axle`` (axle bolt's head seat on
    the -y arm, slider at mid-travel, shank toward +y), ``screw`` (tension screw's head seat on
    the block, shank toward +x).
    """
    part = rail() | slider()
    return set_handles(
        part,
        axle=handle(
            [SLIDER_X0 + T.axle_x, T.head_side * T.width / 2, T.axle_z], [T.axle_head_rot, 0, 0]
        ),
        screw=handle([0, 0, T.screw_z], [0, -90, 0]),
    )


def tension_idler_rail() -> Solid:
    """Print orientation: the rail's plate on the bed."""
    return rail()


def tension_idler_slider() -> Solid:
    """Print orientation: the slider lying on its back."""
    return slider_for_print()


# --- FEM description shared by every part that uses the tensioner -----------------------


@dataclass(frozen=True)
class TensionerRegions:
    """Load, support and limit regions of a tensioner, in its own frame (end block's outer face at
    x = 0, idler axle along y through y = 0, z as in the part's frame, slider at mid-travel)."""

    axle_bore_load: Cylinder  #: the axle bore's wall pushed by the axle
    axle_bore: Cylinder  #: the whole axle bore (the idler's position)
    nut_seat: Box  #: where the tension screw's nut bears on the slider's rear wall
    dovetail: Box  #: the slider's dovetail channel (flanks and roof)
    head_seat: Cylinder  #: the screw head's seat on the end block
    ridge_contact: Box  #: where the slider's plate presses on the ridge
    idler_seat: Box  #: end block and ridge (their displacement moves the idler)


def tensioner_regions(t: TensionIdler = T) -> TensionerRegions:
    """The regions of tensioner ``t``."""
    x0 = slider_x0(t)
    bore_r = TOL.bolt_hole_d(t.axle_m) / 2 + 0.3
    centre = (x0 + t.axle_x, 0.0, t.axle_z)
    channel_half = t.ridge_neck / 2 + t.ridge_h + t.slide_gap * math.sqrt(2) + 0.5
    ridge_half = t.ridge_neck / 2 + t.ridge_h
    head_r = metric(t.screw_m).head_d / 2
    rail_len = x0 + t.travel / 2 + t.plate_len
    return TensionerRegions(
        axle_bore_load=Cylinder(
            centre, (0, 1, 0), bore_r, t.width / 2, facing=(-1, 0, 0), facing_tol_deg=60
        ),
        axle_bore=Cylinder(centre, (0, 1, 0), bore_r, t.width / 2),
        nut_seat=Box(
            (x0 + TOL.nut_wall - 0.3, -3, t.screw_z - 3),
            (x0 + TOL.nut_wall + 0.3, 3, t.screw_z + 3),
            facing=(1, 0, 0),
        ),
        dovetail=Box(
            (x0, -channel_half, t.slider_z0 + 0.3),
            (x0 + t.plate_len, channel_half, t.slider_z0 + t.ridge_h + t.slide_gap + 0.1),
        ),
        head_seat=Cylinder(
            (0, 0, t.screw_z),
            (1, 0, 0),
            head_r,
            0.3,
            inner_radius=TOL.bolt_hole_d(t.screw_m) / 2,
            facing=(-1, 0, 0),
        ),
        ridge_contact=Box(
            (x0, -ridge_half, t.rail_t + 0.3),
            (x0 + t.plate_len, ridge_half, t.rail_t + t.ridge_h + 0.1),
        ),
        idler_seat=Box(
            (0, -ridge_half, t.rail_t),
            (rail_len, ridge_half, t.screw_z + head_r + TOL.min_wall + 0.1),
        ),
    )


@dataclass(frozen=True)
class DovetailPlay:
    """Rigid tilt of the slider allowed by the dovetail clearance, and its effect on the axle."""

    play_mm: float  #: vertical freedom between the plate's two ends
    tilt_rad: float  #: ``play_mm`` over the plate's length
    axle_vertical_mm: float  #: axle's vertical shift when the slider tilts about the plate's front
    axle_along_belt_mm: float  #: axle's shift along the belt


def dovetail_play(t: TensionIdler = T) -> DovetailPlay:
    """Worst-case tilt of the slider on its ridge.

    The belt pulls the axle, which is above the tension screw, so the slider is twisted by a
    couple. Its plate bears with its front end on the rail surface (clearance ``slide_gap``) and
    its rear end on the ridge's flanks (a flank's perpendicular clearance ``slide_gap`` is
    ``slide_gap``·√2 of vertical play), so it tilts by the total play over the plate's length,
    pivoting about the front end. The tilt is rigid: no stiffness, so the FEM cannot find it
    (STATUS.md T3.21).
    """
    play = t.slide_gap * (1 + math.sqrt(2))
    tilt = play / t.plate_len
    return DovetailPlay(
        play,
        tilt,
        tilt * abs(t.axle_x - t.plate_len),
        tilt * (t.axle_z - t.slider_z0),
    )


def _belt_cases(
    belt: BeltLoads, loads: Callable[[float], tuple[str, tuple[Force | Moment, ...]]], source: str
) -> tuple[LoadCase, LoadCase]:
    """Preload (sustained) and peak load cases from a function of the force on the idler."""
    cases = []
    for name, run_n, sustained in (
        ("belt_preload", belt.preload_n, True),
        ("belt_peak", belt.peak_n, False),
    ):
        text, parts = loads(2 * run_n)
        cases.append(
            LoadCase(
                name,
                f"Two belt runs of {run_n:g} N pull the idler along the belt{text}",
                parts,
                source,
                sustained=sustained,
            )
        )
    return cases[0], cases[1]


def _limits(
    prefix: str, region: Box | Cylinder, place: Placement, along_belt: float, other: float
) -> tuple[DisplacementLimit, ...]:
    """Directional displacement limits: along the belt, sideways (axle) and vertical."""
    placed = place.region(region)
    return (
        DisplacementLimit(f"{prefix}_along_belt", placed, along_belt, place.vector((1, 0, 0))),
        DisplacementLimit(f"{prefix}_sideways", placed, other, place.vector((0, 1, 0))),
        DisplacementLimit(f"{prefix}_vertical", placed, other, place.vector((0, 0, 1))),
    )


def slider_fem(
    t: TensionIdler,
    place: Placement,
    belt: BeltLoads,
    source: str,
    along_belt_limit: float = 0.3,
    other_limit: float = 0.1,
) -> FemSpec:
    """FEM spec of a tensioner slider: the belt pulls the axle bore (bearing load), the screw
    nut's seat holds it in x and the dovetail in y and z."""
    r = tensioner_regions(t)
    bore = place.region(r.axle_bore_load)

    def loads(pull: float) -> tuple[str, tuple[Force | Moment, ...]]:
        return "", (Force(bore, place.vector((pull, 0, 0)), bearing=True),)

    return FemSpec(
        load_cases=_belt_cases(belt, loads, source),
        supports=(
            Support(
                "screw_nut_seat",
                place.region(r.nut_seat),
                "Tension screw's nut seat: holds the slider along the belt",
                constrain=_axes(place, (True, False, False)),
            ),
            Support(
                "dovetail",
                place.region(r.dovetail),
                "Dovetail channel on the ridge: holds sideways and vertical, free to slide",
                constrain=_axes(place, (False, True, True)),
            ),
        ),
        displacement_limits=_limits(
            "idler_axle", r.axle_bore, place, along_belt_limit, other_limit
        ),
    )


def _axes(place: Placement, flags: tuple[bool, bool, bool]) -> tuple[bool, bool, bool]:
    """Constraint flags (x, y, z of the tensioner frame) in the part's frame."""
    mapped = place.vector(tuple(1.0 if f else 0.0 for f in flags))
    return (abs(mapped[0]) > 0.5, abs(mapped[1]) > 0.5, abs(mapped[2]) > 0.5)


def mount_fem(
    t: TensionIdler,
    place: Placement,
    belt: BeltLoads,
    source: str,
    supports: tuple[Support, ...],
    along_belt_limit: float = 0.3,
    other_limit: float = 0.1,
) -> FemSpec:
    """FEM spec of a tensioner's mount (end block, ridge and foot): the screw head pushes the
    block with the idler force, and the slider's tilt adds a couple on the ridge because the
    axle sits above the screw. ``supports`` say how the foot is held."""
    r = tensioner_regions(t)
    head, ridge = place.region(r.head_seat), place.region(r.ridge_contact)

    def loads(pull: float) -> tuple[str, tuple[Force | Moment, ...]]:
        couple = pull * (t.axle_z - t.screw_z)
        return (
            "; the screw head pushes the end block with the same force and the slider's dovetail "
            "adds a couple on the ridge because the axle sits above the screw",
            (
                Force(head, place.vector((pull, 0, 0))),
                Moment(ridge, place.vector((0, couple, 0))),
            ),
        )

    return FemSpec(
        load_cases=_belt_cases(belt, loads, source),
        supports=supports,
        displacement_limits=_limits(
            "idler_seat", r.idler_seat, place, along_belt_limit, other_limit
        ),
    )
