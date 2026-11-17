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
Print: PETG; 0.2 mm; 4 perimeters; 40 % infill; rail flat on its plate, slider on its
dovetail lips (underside down); no supports, but the slider's cavity roof bridges ~17 mm.
Dovetail clearance ``slide_gap`` (0.2 mm per side): tune after a test print.
"""

import math
from typing import TYPE_CHECKING

from pythonscad import cube, cylinder, hull, linear_extrude, polygon, union

from plotter_cad.geometry import EPS, FN, FN_HOLE, handle, set_handles, teardrop_x, teardrop_y
from plotter_cad.hardware import metric
from plotter_cad.nut_slot import nut_slot
from plotter_cad.params import TENSION_IDLER, TOL, TensionIdler

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

    axle_hole = teardrop_y(TOL.bolt_hole_d(t.axle_m), w + 2).translate([x0 + t.axle_x, 0, t.axle_z])
    axle_nut = (
        cylinder(d=TOL.nut_trap_ac(t.axle_m), h=TOL.nut_trap_h(t.axle_m) + 1, fn=6)
        .rotate([0, 0, 90])
        .rotate([-90, 0, 0])
        .translate([x0 + t.axle_x, t.nut_y, t.axle_z])
    )
    nut_t = TOL.nut_trap_h(t.screw_m)
    screw_nut = nut_slot(t.screw_m, arm_top - t.screw_z + 1, "x", "+z").translate(
        [x0 + TOL.nut_wall + nut_t / 2, 0, t.screw_z]
    )
    screw_hole = teardrop_x(TOL.bolt_hole_d(t.screw_m), 2 * length).translate(
        [x0 + length / 2, 0, t.screw_z]
    )
    cut = _cavity(t, t.plate_len).translate([x0, 0, 0])
    return body - cut - axle_hole - axle_nut - screw_nut - screw_hole


def slider_for_print(t: TensionIdler = T) -> Solid:
    """The slider in print orientation: its dovetail lips on the bed, arms up."""
    return slider(t).translate([-slider_x0(t), 0, -t.slider_z0])


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
    """Print orientation: the slider's dovetail lips on the bed, arms up."""
    return slider_for_print()
