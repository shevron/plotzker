"""PSU terminal hood: closes the supply's terminal end and carries the mains inlet and the DC
connector (T3.31, D38). Print ×1.

Purpose: a box over the terminal end, so nothing live can be touched. It reaches back over the
case: a sleeve over the fan face past the open strip in front of the cover (the terminal screws
are reached from there), a short one over the bottom face, and narrow screw tabs over the label
and switch walls to the y = 32 M4 holes, which hold the hood (three M4, so it only comes off
with a tool); the case's own vents beside the tabs stay open.

There is no partition between the mains and the 24 V wiring (agreed after the first print):
that rests on the insulated fork lugs, push-on sleeves and wire insulation.

The C14 inlet (fuse, lighted switch) sits in the outer wall, facing out from the machine, its
long side across the case, clear of the XT60 behind it; its flange reaches onto the fan-side
sleeve. The XT60H-F female sits low in the board-side wall, below the board's underside, so its
plug and cable run under the board straight to the ZRIB. It is pushed in from inside the open
hood until its collar stops on a 0.8 lip, press-fit in its window and pocket, its front section
standing 7.2 out (keyed: its
chamfered side goes toward the PSU). A drop of hot glue behind it keeps plugging in from
pushing it back.

  section in front of the PSU (PSU frame: x down the PSU from the label wall, z out of the
  bottom face; the board is to the left)

     z = -2 (board side)        z = 52 (outer wall)
     ┌────────────────────────────┐ x = -2 (label wall, up)
     │                            │
     │                     ┌──────┤
     │                     │inlet ▶   (switch faces out)
     ◀ XT60                └──────┤
     └────────────────────────────┘ x = 115 (switch wall, down)

Frame: the PSU frame (``hardware/psu.py``). :func:`psu_hood_installed` returns the hood there;
:func:`psu_hood` in print orientation (front wall down).

Hardware:
  3 × M4×6 ISO 4762 through the tabs into the case (they enter 4 mm): 1 in the label wall,
      2 in the switch wall
  1 × C14 inlet with fuse and switch; 2 × M3×10 ISO 4762 + 2 × M3 nuts (pressed into the
      bosses from inside)
  1 × XT60 female (pushed through the board-side wall from inside)

Fit: print the XT60 test piece first when changing the fit (``params.PSU_MOUNT.xt60_*``).

Print: default profile; front wall down; no supports: the walls are vertical, the XT60 sleeve
has a 45° underside; the only bridges are the inlet cutout's top edge (48 mm), the XT60
pocket's (10 mm) and the teardrop holes.
"""

from typing import TYPE_CHECKING

from cadder.geometry import EPS, FN_HOLE, box, teardrop
from cadder.handles import handle, set_handles
from cadder.types import Matrix
from pythonscad import circle, cylinder, hull, linear_extrude, polygon, square, union

from plotzker.hardware import C14_INLET, PSU
from plotzker.params import PSU_MOUNT, TOL

if TYPE_CHECKING:
    from pythonscad import Solid

HOOD_SCREW_Y = PSU.hole_y[0]


def _hole_x(d: float, x0: float, x1: float, y: float, z: float) -> Solid:
    """Hole along x (teardrop pointing +y, up in the print)."""
    return linear_extrude(teardrop(d), height=x1 - x0).rotate([0, 90, 0]).translate([x0, y, z])


def _hole_z(d: float, x: float, y: float, z0: float, z1: float) -> Solid:
    """Hole along z (teardrop pointing +y)."""
    return linear_extrude(teardrop(d), height=z1 - z0).translate([x, y, z0])


def _inlet_holes() -> list[tuple[float, float]]:
    """The inlet's screw holes in PSU (x, y): its long side runs along x, its short side (where
    the holes are) along y."""
    m = PSU_MOUNT
    return [(m.inlet_x + long, m.inlet_y + short) for long, short in C14_INLET.hole_xy]


def _xt60_box(size: tuple[float, float], grow: float, z0: float, z1: float) -> Solid:
    """A box of ``size`` (along x, along y) plus ``grow`` per side round the XT60's axis."""
    m = PSU_MOUNT
    sx, sy = size
    return box(
        m.xt60_x - sx / 2 - grow,
        m.xt60_y - sy / 2 - grow,
        z0,
        m.xt60_x + sx / 2 + grow,
        m.xt60_y + sy / 2 + grow,
        z1,
    )


def _xt60_window(z0: float, z1: float) -> Solid:
    """The lip's window: the front section's outline, its +y corners chamfered (the key)."""
    m = PSU_MOUNT
    sx, sy = m.xt60_window
    k = m.xt60_key
    outline = polygon(
        [
            [-sx / 2, -sy / 2],
            [sx / 2, -sy / 2],
            [sx / 2, sy / 2 - k],
            [sx / 2 - k, sy / 2],
            [-sx / 2 + k, sy / 2],
            [-sx / 2, sy / 2 - k],
        ]
    )
    return linear_extrude(outline, height=z1 - z0).translate([m.xt60_x, m.xt60_y, z0])


def _xt60_collar_pocket(z0: float, z1: float) -> Solid:
    """The pocket gripping the collar: its +y corners rounded, as the collar's."""
    m = PSU_MOUNT
    sx, sy = m.xt60_pocket
    r = m.xt60_pocket_r
    corners = union(
        *(circle(r=r, fn=32).translate([s * (sx / 2 - r), sy / 2 - r]) for s in (-1, 1))
    )
    outline = hull(union(square([sx, sy - r]).translate([-sx / 2, -sy / 2]), corners))
    return linear_extrude(outline, height=z1 - z0).translate([m.xt60_x, m.xt60_y, z0])


def _handles() -> dict[str, Matrix | list[Matrix]]:
    """Handles for the hardware (PSU frame)."""
    m = PSU_MOUNT
    ox0, _, _, ox1 = m.hood_x
    oz0, _, iz1, oz1 = m.hood_z
    return {
        "inlet": handle([m.inlet_x, m.inlet_y, oz1]),
        "inlet_screws": [handle([x, y, oz1 + C14_INLET.flange_t]) for x, y in _inlet_holes()],
        #: a corner of each nut points +y, as its pocket
        "inlet_nuts": [handle([x, y, iz1 - m.inlet_boss_t], [0, 0, 90]) for x, y in _inlet_holes()],
        #: mating face out toward the board (-z), the collar on the lip
        "xt60": handle([m.xt60_x, m.xt60_y, oz0 - m.xt60_protrude], [-90, 0, 90]),
        "label_screws": [handle([ox0, HOOD_SCREW_Y, PSU.label_hole_z], [0, -90, 0])],
        "switch_screws": [handle([ox1, HOOD_SCREW_Y, z], [0, 90, 0]) for z in PSU.switch_hole_z],
    }


def _shell() -> Solid:
    """The box in front of the wall ends, the sleeves over the fan and bottom faces and the
    side screw tabs."""
    m = PSU_MOUNT
    ox0, ix0, ix1, ox1 = m.hood_x
    oz0, iz0, iz1, oz1 = m.hood_z
    d, t = m.depth, m.wall_t
    front = box(ox0, -d, oz0, ox1, 0, oz1) - box(ix0, -d + t, iz0, ix1, 1, iz1)
    fan = box(ox0, -EPS, iz1, ox1, m.sleeve_fan, oz1)
    bottom = box(ox0, -EPS, oz0, ox1, m.sleeve_bottom, iz0)
    tm = m.tab_margin
    label = box(ox0, -EPS, PSU.label_hole_z - tm, ix0, m.sleeve_side, PSU.label_hole_z + tm)
    zs = PSU.switch_hole_z
    switch = box(ix1, -EPS, min(zs) - tm, ox1, m.sleeve_side, max(zs) + tm)
    return union(front, fan, bottom, label, switch)


def _xt60_sleeve() -> Solid:
    """Sleeve round the XT60's collar inside the board-side wall, with a 45° underside (-y,
    down in the print)."""
    m = PSU_MOUNT
    iz0 = m.hood_z[1]
    s, t = m.xt60_sleeve, m.wall_t
    sx, sy = m.xt60_pocket
    sleeve = _xt60_box((sx, sy), t, iz0 - EPS, iz0 + s)
    y0 = m.xt60_y - sy / 2 - t
    wedge = (
        linear_extrude(
            polygon([[y0 + EPS, iz0 - EPS], [y0 + EPS, iz0 + s], [y0 - s, iz0 - EPS]]),
            height=sx + 2 * t,
        )
        .rotate([90, 0, 90])
        .translate([m.xt60_x - sx / 2 - t, 0, 0])
    )
    return sleeve | wedge


def _inlet_bosses() -> Solid:
    """Bosses inside the outer wall for the inlet's M3 nuts."""
    m = PSU_MOUNT
    iz1 = m.hood_z[2]
    return union(
        *(
            cylinder(d=C14_INLET.ear_d, h=m.inlet_boss_t + EPS, fn=FN_HOLE).translate(
                [x, y, iz1 - m.inlet_boss_t]
            )
            for x, y in _inlet_holes()
        )
    )


def psu_hood_installed() -> Solid:
    """The hood in the PSU frame."""
    m = PSU_MOUNT
    ox0, ix0, ix1, ox1 = m.hood_x
    oz0, iz0, iz1, oz1 = m.hood_z
    body = _shell() | _xt60_sleeve() | _inlet_bosses()
    # inlet cutout in the outer wall: long side along x
    cl, cs = C14_INLET.cutout
    f = 0.25
    body = body - box(
        m.inlet_x - cl / 2 - f,
        m.inlet_y - cs / 2 - f,
        iz1 - m.inlet_boss_t - 1,
        m.inlet_x + cl / 2 + f,
        m.inlet_y + cs / 2 + f,
        oz1 + 1,
    )
    nut_ac, nut_t = TOL.nut_trap_ac(C14_INLET.hole_m), TOL.nut_trap_h(C14_INLET.hole_m)
    for x, y in _inlet_holes():
        body = body - _hole_z(
            TOL.bolt_hole_d(C14_INLET.hole_m), x, y, iz1 - m.inlet_boss_t - 1, oz1 + 1
        )
        # nut pressed in from inside; a corner points +y (up in the print)
        body = body - cylinder(d=nut_ac, h=nut_t + 1, fn=6).rotate([0, 0, 90]).translate(
            [x, y, iz1 - m.inlet_boss_t - 1]
        )
    # XT60: the keyed window through the lip, then the pocket for its collar and rim
    lip = oz0 + m.xt60_lip
    body = body - _xt60_window(oz0 - 1, lip + EPS)
    body = body - _xt60_collar_pocket(lip, iz0 + m.xt60_sleeve + 1)
    # M4 through the tabs into the case
    m4 = TOL.bolt_hole_d(PSU.hole_m)
    body = body - _hole_x(m4, ox0 - 1, ix0 + 1, HOOD_SCREW_Y, PSU.label_hole_z)
    for z in PSU.switch_hole_z:
        body = body - _hole_x(m4, ix1 - 1, ox1 + 1, HOOD_SCREW_Y, z)
    return set_handles(body, **_handles())


def psu_hood() -> Solid:
    """The hood in print orientation: front wall down."""
    return psu_hood_installed().rotate([90, 0, 0]).translate([0, 0, PSU_MOUNT.depth])
