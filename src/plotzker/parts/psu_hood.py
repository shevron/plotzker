"""PSU terminal hood: closes the supply's terminal end and carries the mains inlet and the DC
connector (T3.31, D38). Print ×1.

Purpose: a box over the terminal end, so nothing live can be touched. Sleeves reach back
over the case: over the fan face past the open strip in front of the cover (the terminal
screws are reached from there), and over the label and switch walls to the y = 32 M4 holes,
which hold the hood (three M4, so it only comes off with a tool). Windows in the side sleeves
leave the case's own vent slots near the terminal end open (they open onto the case wall).

Inside, a partition keeps the mains wiring away from the 24 V side: a floor (z = 22, above the
wire lugs) runs from the wall ends to the front wall, with the DC channel under it along the
board side and the mains above; beside PE/N/L a wall between the last -V terminal and PE closes
the mains column, which reaches under the floor only in front of its own lugs.

The C14 inlet (fuse, lighted switch) sits in the outer wall on the mains side, facing out from
the machine; in front of the PSU the hood stands out past the fan face to give its body and
connectors room. The XT60 female sits low in the board-side wall, below the board's underside,
so its plug and cable run under the board straight to the ZRIB; a zip-tie post beside it takes
its wires.

  section in front of the PSU (PSU frame: x down the PSU from the label wall, z out of the
  bottom face; the board is to the left)

     z = -3 (board side)         z = 70 (outer wall, bulged)
     ┌──────────┬─────────────────┐ x = -3 (label wall, up)
     │ DC       │                 │
     │ channel  │  mains          │
     │          │          ┌──────┤
     ◀ XT60     │          │inlet ▶   (switch faces out)
     │          │          └──────┤
     └──────────┴─────────────────┘ x = 116 (switch wall, down)
              floor (z = 22)

Frame: the PSU frame (``hardware/psu.py``). :func:`psu_hood_installed` returns the hood there;
:func:`psu_hood` in print orientation (front wall down).

Hardware:
  3 × M4×6 ISO 4762 through the sleeves into the case (they enter 3 mm): 1 in the label wall,
      2 in the switch wall
  1 × C14 inlet with fuse and switch; 2 × M3×10 ISO 4762 + 2 × M3 nuts (pressed into the
      bosses from inside)
  1 × XT60 female (pushed through the board-side wall from inside), 1 zip tie

Not measured yet (ASSUMED in ``hardware/psu.py``): the inlet's cutout, flange and screw
holes, and the XT60's body. Check both before printing.

Print: default profile; front wall down; no supports (holes across the print are teardrops; the
inlet cutout's top edge and the step of the mains column bridge about 48 and 33 mm).
"""

from typing import TYPE_CHECKING

from cadder.geometry import EPS, FN_HOLE, box, teardrop
from cadder.handles import handle, set_handles
from cadder.types import Matrix
from pythonscad import cylinder, linear_extrude, union

from plotzker.hardware import C14_INLET, PSU, XT60
from plotzker.params import PSU_MOUNT, TOL

if TYPE_CHECKING:
    from pythonscad import Solid

#: Windows in the side sleeves over the case's vent slots near the terminal end (y, z)
SIDE_WINDOW_Y = (3.5, 24.5)
SIDE_WINDOW_Z = (8, 36)
HOOD_SCREW_Y = PSU.hole_y[0]


def _hole_x(d: float, x0: float, x1: float, y: float, z: float) -> Solid:
    """Hole along x (teardrop pointing +y, up in the print)."""
    return linear_extrude(teardrop(d), height=x1 - x0).rotate([0, 90, 0]).translate([x0, y, z])


def _hole_z(d: float, x: float, y: float, z0: float, z1: float) -> Solid:
    """Hole along z (teardrop pointing +y)."""
    return linear_extrude(teardrop(d), height=z1 - z0).translate([x, y, z0])


def _inlet_holes() -> list[tuple[float, float]]:
    """The inlet's screw holes in PSU (x, y): the long side of the cutout runs along x."""
    m = PSU_MOUNT
    return [(m.inlet_x + dx, m.inlet_y + dy) for dx, dy in C14_INLET.hole_xy]


def _xt60_box(grow: float, z0: float, z1: float) -> Solid:
    """The XT60's outline in the board-side wall grown by ``grow`` per side, from z0 to z1: the
    body's height (8.2) along x, its width (15.5) along y."""
    m = PSU_MOUNT
    w, h = XT60.body
    return box(
        m.xt60_x - h / 2 - grow,
        m.xt60_y - w / 2 - grow,
        z0,
        m.xt60_x + h / 2 + grow,
        m.xt60_y + w / 2 + grow,
        z1,
    )


def _handles() -> dict[str, Matrix | list[Matrix]]:
    """Handles for the hardware (PSU frame)."""
    m = PSU_MOUNT
    ox0, _, _, ox1 = m.hood_x
    oz0 = m.hood_z[0]
    fz_in, fz_out = m.front_z
    return {
        "inlet": handle([m.inlet_x, m.inlet_y, fz_out]),
        "inlet_screws": [handle([x, y, fz_out + C14_INLET.flange_t]) for x, y in _inlet_holes()],
        #: a corner of each nut points +y, as its pocket
        "inlet_nuts": [
            handle([x, y, fz_in - m.inlet_boss_t], [0, 0, 90]) for x, y in _inlet_holes()
        ],
        #: mating face out toward the board (-z), resting on the window's side
        "xt60": handle([m.xt60_x - m.xt60_fit, m.xt60_y, oz0 - XT60.protrude], [-90, 0, 90]),
        "label_screws": [handle([ox0, HOOD_SCREW_Y, PSU.label_hole_z], [0, -90, 0])],
        "switch_screws": [handle([ox1, HOOD_SCREW_Y, z], [0, 90, 0]) for z in PSU.switch_hole_z],
    }


def _shell() -> Solid:
    """The box in front of the wall ends (bulged out past the fan face) and the sleeves."""
    m = PSU_MOUNT
    ox0, ix0, ix1, ox1 = m.hood_x
    oz0, iz0, iz1, oz1 = m.hood_z
    fz_in, fz_out = m.front_z
    d, t = m.depth, m.wall_t
    front = box(ox0, -d, oz0, ox1, 0, fz_out)
    # open toward the PSU below its fan face; above it a back wall closes the bulge
    front = front - box(ix0, -d + t, iz0, ix1, 1, iz1) - box(ix0, -d + t, iz0, ix1, -t, fz_in)
    fan = box(ox0, -EPS, iz1, ox1, m.sleeve_fan, oz1)
    label = box(ox0, -EPS, oz0, ix0, m.sleeve_side, oz1)
    switch = box(ix1, -EPS, oz0, ox1, m.sleeve_side, oz1)
    bottom = box(ox0, -EPS, oz0, ox1, m.sleeve_bottom, iz0)
    shell = front | fan | label | switch | bottom
    # windows over the case's own vent slots (they open onto the case wall, not into the hood)
    wy, wz = SIDE_WINDOW_Y, SIDE_WINDOW_Z
    shell = shell - box(ox0 - 1, wy[0], wz[0], ix0 + EPS, wy[1], wz[1])
    shell = shell - box(ix1 - EPS, wy[0], wz[0], ox1 + 1, wy[1], wz[1])
    return shell


def _partition() -> Solid:
    """DC/mains partition: a floor over the DC channel, and the wall and step that close the
    mains column in front of PE/N/L (which reaches under the floor)."""
    m = PSU_MOUNT
    _, ix0, ix1, _ = m.hood_x
    iz0 = m.hood_z[1]
    bt, xn, sy, zd = m.barrier_t, m.barrier_x_near, m.barrier_step_y, m.dc_channel_z
    gap = m.barrier_front_gap
    y_front = -m.depth + m.wall_t - EPS
    return union(
        box(ix0 - EPS, y_front, zd, xn, -gap, zd + bt),  # floor beside the DC lugs
        box(xn, y_front, zd, ix1 + EPS, -sy, zd + bt),  # floor in front of the mains column
        box(xn - bt / 2, -sy - bt, iz0 - EPS, xn + bt / 2, -gap, zd + bt),  # between -V and PE
        box(xn, -sy - bt, iz0 - EPS, ix1 + EPS, -sy, zd + bt),  # the column's front (a bridge)
    )


def _xt60_mount() -> Solid:
    """Grip sleeve round the XT60 inside the board-side wall, and a zip-tie post beside it."""
    m = PSU_MOUNT
    iz0 = m.hood_z[1]
    f, t = m.xt60_fit, m.wall_t
    sleeve = _xt60_box(f + t, iz0 - EPS, iz0 + m.xt60_sleeve)
    # the post stands across the DC channel, on the label-wall side of the sleeve
    pw, pt = m.tie_bar
    post_x = m.xt60_x - XT60.body[1] / 2 - f - t - 4 - pw
    post = box(
        post_x, m.xt60_y - pt / 2, iz0 - EPS, post_x + pw, m.xt60_y + pt / 2, m.dc_channel_z + EPS
    )
    return sleeve | post


def _inlet_bosses() -> Solid:
    """Bosses inside the outer wall for the inlet's M3 nuts."""
    m = PSU_MOUNT
    fz_in = m.front_z[0]
    return union(
        *(
            cylinder(d=C14_INLET.ear_d, h=m.inlet_boss_t + EPS, fn=FN_HOLE).translate(
                [x, y, fz_in - m.inlet_boss_t]
            )
            for x, y in _inlet_holes()
        )
    )


def psu_hood_installed() -> Solid:
    """The hood in the PSU frame."""
    m = PSU_MOUNT
    ox0, ix0, ix1, ox1 = m.hood_x
    oz0, iz0 = m.hood_z[:2]
    fz_in, fz_out = m.front_z
    body = _shell() | _partition() | _xt60_mount() | _inlet_bosses()
    # inlet cutout in the outer wall
    cw, ch = C14_INLET.cutout
    f = 0.25
    body = body - box(
        m.inlet_x - cw / 2 - f,
        m.inlet_y - ch / 2 - f,
        fz_in - m.inlet_boss_t - 1,
        m.inlet_x + cw / 2 + f,
        m.inlet_y + ch / 2 + f,
        fz_out + 1,
    )
    nut_ac, nut_t = TOL.nut_trap_ac(C14_INLET.hole_m), TOL.nut_trap_h(C14_INLET.hole_m)
    for x, y in _inlet_holes():
        body = body - _hole_z(
            TOL.bolt_hole_d(C14_INLET.hole_m), x, y, fz_in - m.inlet_boss_t - 1, fz_out + 1
        )
        # nut pressed in from inside; a corner points +y (up in the print)
        body = body - cylinder(d=nut_ac, h=nut_t + 1, fn=6).rotate([0, 0, 90]).translate(
            [x, y, fz_in - m.inlet_boss_t - 1]
        )
    # XT60 window through the board-side wall and its sleeve
    body = body - _xt60_box(m.xt60_fit, oz0 - 1, iz0 + m.xt60_sleeve + 1)
    # M4 through the sleeves into the case
    m4 = TOL.bolt_hole_d(PSU.hole_m)
    body = body - _hole_x(m4, ox0 - 1, ix0 + 1, HOOD_SCREW_Y, PSU.label_hole_z)
    for z in PSU.switch_hole_z:
        body = body - _hole_x(m4, ix1 - 1, ox1 + 1, HOOD_SCREW_Y, z)
    return set_handles(body, **_handles())


def psu_hood() -> Solid:
    """The hood in print orientation: front wall down."""
    return psu_hood_installed().rotate([90, 0, 0]).translate([0, 0, PSU_MOUNT.depth])
