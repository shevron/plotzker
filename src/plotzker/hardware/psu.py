"""The 24 V supply (Cheng Liang P360W24V), its C14 mains inlet and the XT60 DC connector.

Source of values: docs/hardware.md (PSU: the user's caliper readings, the rest from photos by
the photo-metrologist, ``photos/psu/report.md``). The inlet is measured (its push-on tabs are
ASSUMED); the XT60 is not measured yet (ASSUMED nominal size): check it before printing.

PSU frame (as in docs/hardware.md): origin at the corner where the terminal end, the label
wall and the bottom face meet; ``x`` across toward the switch wall (0..113), ``y`` from the
terminal end (the side walls' ends) to the fan end (0..215), ``z`` from the bottom face (the
face without the fan) to the fan face (0..50). The terminal block's screws point +z; the wire
lugs leave it toward -y.

Inlet frame: origin at the center of the cutout on the panel's outer face, the long side of the
cutout along ``x``, the body behind the panel along -z. XT60 frame: origin at the center of the
mating face, the body along -y (toward the wires).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cadder.geometry import box
from pythonscad import cube, cylinder, linear_extrude, polygon, union

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True)
class PsuSpec:
    """The supply's case, holes, terminals and keep-outs (PSU frame)."""

    size: tuple[float, float, float] = (113, 215, 50)  #: x × y × z (measured)
    mass_kg: float = 0.77  #: with the inlet and its wires (weighed by the user)
    # M4 mounting holes (measured)
    hole_m: float = 4
    hole_y: tuple[float, float] = (32, 182)  #: the same two lines on every face
    bottom_hole_x: tuple[float, float] = (31.5, 81.5)  #: bottom face (z = 0)
    label_hole_z: float = 10.5  #: label wall (x = 0): one hole per line
    switch_hole_z: tuple[float, float] = (11.5, 36.5)  #: switch wall (x = 113)
    #: DESIGN: how deep a screw may enter the case past the sheet (parts sit behind it)
    max_screw_depth: float = 5
    # Terminal end (photo except where marked)
    terminal_count: int = 9  #: +V ×3, -V ×3, PE, N, L from the label wall
    terminal_x0: float = 27.4  #: first screw's x
    terminal_pitch: float = 9.6
    block_x: tuple[float, float] = (21.5, 108.5)
    block_front_y: float = 1.6  #: the walls stick out this far past the block (measured)
    block_back_y: float = 15.5
    block_z: tuple[float, float] = (6, 20)
    screw_top_z: float = 18  #: terminal screw heads (measured: ~32 below the fan face)
    cover_setback: float = 18.4  #: the fan-face cover stops this far from the wall ends
    #: wire lugs and wires leave the block toward -y: keep-out in front of the wall ends
    crimp_reach: float = 8.5  #: past the wall ends (y = 0)
    crimp_x: tuple[float, float] = (22, 110)
    crimp_z: tuple[float, float] = (5, 20)
    lug_w: float = 6.5  #: width of one blue fork lug's barrel
    #: terminals with a wire: +V3, -V1, PE, N, L (the user's wiring; indices from the label wall)
    wired: tuple[int, ...] = (2, 3, 6, 7, 8)
    hole_depth: float = 6  #: modeled depth of the M4 holes (sheet and the nut behind it)
    # 115/230 V selector on the switch wall (measured)
    selector_y: tuple[float, float] = (122, 137)
    selector_z: tuple[float, float] = (11, 19)
    # Vents to keep open (photo): rows of slots along both long edges of the bottom face
    bottom_vent_y: tuple[float, float] = (35, 188.5)
    bottom_vent_w: float = 20  #: from each long edge, running round the bend

    @property
    def terminal_xs(self) -> tuple[float, ...]:
        """Screw centers across the block (+V1 ... L)."""
        return tuple(self.terminal_x0 + i * self.terminal_pitch for i in range(self.terminal_count))

    @property
    def dc_mains_gap_x(self) -> float:
        """Midway between the last -V terminal and PE: where DC and mains part."""
        xs = self.terminal_xs
        return (xs[5] + xs[6]) / 2


PSU = PsuSpec()


@dataclass(frozen=True)
class C14InletSpec:
    """Screw-mounted C14 inlet with fuse drawer and lighted rocker switch (measured by the user,
    T3.31, except where marked).

    The flange is an elongated hexagon with rounded corners: flat ends across the body's long
    side, pointed across its short side, where the two screw holes sit. Behind the flange the
    body's side walls turn diagonal at the bottom (the C14 socket's shape) and narrow to 15.2;
    the push-on tabs stand out behind that (not measured).
    """

    cutout: tuple[float, float] = (47.3, 27.3)  #: the body: long × short side (measured)
    body_h: float = 16.7  #: body behind the flange (measured)
    tabs: float = 9  #: ASSUMED: the push-on tabs behind the body
    flange: tuple[float, float] = (58.8, 49.5)  #: across the flats (long) × across the points
    flange_flat: float = 32  #: ASSUMED: length of the flat ends (the hexagon's short sides)
    flange_t: float = 2.2
    #: screw holes: (long, short) offsets from the center: at the pointed ends, 40 apart
    hole_xy: tuple[tuple[float, float], ...] = ((0, 20), (0, -20))
    hole_d: float = 4  #: the flange's holes (measured): M3 screws
    hole_m: float = 3
    ear_d: float = 9  #: boss round each screw inside the hood
    #: room the push-on connectors and the bends of their wires need behind the tabs (ASSUMED)
    connector_room: float = 15

    @property
    def depth(self) -> float:
        """Body plus tabs behind the panel."""
        return self.body_h + self.tabs


C14_INLET = C14InletSpec()


@dataclass(frozen=True)
class Xt60Spec:
    """XT60 female (the PSU side). ASSUMED: nominal XT60 size, not measured."""

    body: tuple[float, float] = (15.5, 8.2)  #: across × high at the mating face
    chamfer: float = 1.5  #: two corners of one long side are cut at 45° (the polarity key)
    length: float = 16  #: mating face to the solder cups
    protrude: float = 8  #: stands out of the panel so the male's shroud can slide over it
    wire_d: float = 4.5  #: 12 AWG silicone wire, outer diameter


XT60 = Xt60Spec()


def psu() -> Solid:
    """The supply in the PSU frame: case, terminal block and the lugs' keep-out."""
    p = PSU
    sx, sy, sz = p.size
    case = cube([sx, sy, sz])
    # open end: the cover stops short on the fan side, the block sits inside the walls
    pocket = box(1, -1, 1, sx - 1, p.cover_setback, sz + 1)
    block = box(
        p.block_x[0], p.block_front_y, p.block_z[0], p.block_x[1], p.block_back_y, p.block_z[1]
    )
    xs = p.terminal_xs
    lugs = union(
        *(
            box(
                xs[i] - p.lug_w / 2,
                -p.crimp_reach,
                p.crimp_z[0],
                xs[i] + p.lug_w / 2,
                p.block_front_y,
                p.crimp_z[1],
            )
            for i in p.wired
        )
    )
    case = case - pocket
    d, r = p.hole_depth, p.hole_m / 2
    for y in p.hole_y:
        for x in p.bottom_hole_x:
            case = case - cylinder(r=r, h=d + 1, fn=16).translate([x, y, -1])
        for z in (p.label_hole_z,):
            case = case - cylinder(r=r, h=d + 1, fn=16).rotate([0, 90, 0]).translate([-1, y, z])
        for z in p.switch_hole_z:
            case = case - cylinder(r=r, h=d + 1, fn=16).rotate([0, 90, 0]).translate([sx - d, y, z])
    return union(case.color("Silver"), block.color("#222"), lugs.color("RoyalBlue", 0.5))


def c14_inlet() -> Solid:
    """The inlet in its own frame: flange on the panel (z ≥ 0), body behind it (z < 0)."""
    i = C14_INLET
    lx, wy = i.flange[0] / 2, i.flange[1] / 2
    fy = i.flange_flat / 2
    outline = polygon([[-lx, -fy], [0, -wy], [lx, -fy], [lx, fy], [0, wy], [-lx, fy]])
    flange = linear_extrude(outline, height=i.flange_t)
    for x, y in i.hole_xy:
        flange = flange - cylinder(d=i.hole_d, h=i.flange_t + 2, fn=16).translate([x, y, -1])
    body = cube([*i.cutout, i.body_h]).translate([-i.cutout[0] / 2, -i.cutout[1] / 2, -i.body_h])
    tabs = cube([i.cutout[0] - 10, 15.2, i.tabs]).translate([-i.cutout[0] / 2 + 5, -7.6, -i.depth])
    return (flange | body | tabs).color("#111")


def xt60_female() -> Solid:
    """The XT60 female in its own frame: mating face at y = 0, body toward -y."""
    x = XT60
    w, h = x.body
    return cube([w, x.length, h]).translate([-w / 2, -x.length, -h / 2]).color("Gold")
