"""The 24 V supply (Cheng Liang P360W24V), its C14 mains inlet and the XT60 DC connector.

Source of values: docs/hardware.md (PSU: the user's caliper readings, the rest from photos by
the photo-metrologist, ``photos/psu/report.md``). The inlet is measured (its push-on tabs are
ASSUMED); the XT60H-F's cross-sections are measured.

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
from pythonscad import circle, cube, cylinder, hull, linear_extrude, polygon, square, union

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


PSU_SPEC = PsuSpec()


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


C14_INLET_SPEC = C14InletSpec()


@dataclass(frozen=True)
class Xt60Spec:
    """Amass XT60H-F, the female on the PSU side. Cross-sections measured by the user (caliper,
    after the first test piece); lengths and the rim from photos (photos/xt60/report.md) and the
    Amass drawing. Sizes are width (across the long side) × height; positions run from the
    mating face back toward the wires.
    """

    front: tuple[float, float] = (13.9, 6.4)  #: the mating section (measured)
    front_len: float = 8.0  #: to the collar's shoulder (7.2 proud of a 0.8 lip, measured)
    chamfer: float = 2.2  #: 45°, both corners of one short side (2.0 flat between, measured)
    collar: tuple[float, float] = (15.5, 8.1)  #: the lettered collar (measured)
    collar_r: float = 1.5  #: its two corners on the chamfered side (measured, roughly)
    collar_len: float = 3.8  #: its front shoulder to the rim (measured)
    flange: tuple[float, float] = (16.4, 9.2)  #: the rim behind the collar (Amass drawing)
    flange_len: float = 0.8
    cap: tuple[float, float] = (15.6, 6.5)  #: black rear cap (photo, ±1)
    length: float = 23.4  #: mating face to the back of the cap
    wire_room: float = 10  #: straight wire behind the cap before it may bend


XT60_SPEC = Xt60Spec()


def psu() -> Solid:
    """The supply in the PSU frame: case, terminal block and the lugs' keep-out."""
    sx, sy, sz = PSU_SPEC.size
    case = cube([sx, sy, sz])
    # open end: the cover stops short on the fan side, the block sits inside the walls
    pocket = box(1, -1, 1, sx - 1, PSU_SPEC.cover_setback, sz + 1)
    block = box(
        PSU_SPEC.block_x[0],
        PSU_SPEC.block_front_y,
        PSU_SPEC.block_z[0],
        PSU_SPEC.block_x[1],
        PSU_SPEC.block_back_y,
        PSU_SPEC.block_z[1],
    )
    xs = PSU_SPEC.terminal_xs
    lugs = union(
        *(
            box(
                xs[i] - PSU_SPEC.lug_w / 2,
                -PSU_SPEC.crimp_reach,
                PSU_SPEC.crimp_z[0],
                xs[i] + PSU_SPEC.lug_w / 2,
                PSU_SPEC.block_front_y,
                PSU_SPEC.crimp_z[1],
            )
            for i in PSU_SPEC.wired
        )
    )
    case = case - pocket
    d, r = PSU_SPEC.hole_depth, PSU_SPEC.hole_m / 2
    for y in PSU_SPEC.hole_y:
        for x in PSU_SPEC.bottom_hole_x:
            case = case - cylinder(r=r, h=d + 1, fn=16).translate([x, y, -1])
        for z in (PSU_SPEC.label_hole_z,):
            case = case - cylinder(r=r, h=d + 1, fn=16).rotate([0, 90, 0]).translate([-1, y, z])
        for z in PSU_SPEC.switch_hole_z:
            case = case - cylinder(r=r, h=d + 1, fn=16).rotate([0, 90, 0]).translate([sx - d, y, z])
    return union(case.color("Silver"), block.color("#222"), lugs.color("RoyalBlue", 0.5))


def c14_inlet() -> Solid:
    """The inlet in its own frame: flange on the panel (z ≥ 0), body behind it (z < 0)."""
    lx, wy = C14_INLET_SPEC.flange[0] / 2, C14_INLET_SPEC.flange[1] / 2
    fy = C14_INLET_SPEC.flange_flat / 2
    outline = polygon([[-lx, -fy], [0, -wy], [lx, -fy], [lx, fy], [0, wy], [-lx, fy]])
    flange = linear_extrude(outline, height=C14_INLET_SPEC.flange_t)
    for x, y in C14_INLET_SPEC.hole_xy:
        flange = flange - cylinder(d=C14_INLET_SPEC.hole_d, h=C14_INLET_SPEC.flange_t + 2, fn=16).translate([x, y, -1])
    body = cube([*C14_INLET_SPEC.cutout, C14_INLET_SPEC.body_h]).translate(
        [-C14_INLET_SPEC.cutout[0] / 2, -C14_INLET_SPEC.cutout[1] / 2, -C14_INLET_SPEC.body_h]
    )
    tabs = cube([C14_INLET_SPEC.cutout[0] - 10, 15.2, C14_INLET_SPEC.tabs]).translate(
        [-C14_INLET_SPEC.cutout[0] / 2 + 5, -7.6, -C14_INLET_SPEC.depth]
    )
    return (flange | body | tabs).color("#111")


def xt60_female() -> Solid:
    """The XT60H-F in its own frame: mating face at y = 0, body toward -y, width along x (the
    chamfered short side toward +x), height along z."""
    w, h, c = *XT60_SPEC.front, XT60_SPEC.chamfer
    outline = polygon(
        [
            [-w / 2, -h / 2],
            [w / 2 - c, -h / 2],
            [w / 2, -h / 2 + c],
            [w / 2, h / 2 - c],
            [w / 2 - c, h / 2],
            [-w / 2, h / 2],
        ]
    )
    front = linear_extrude(outline, height=XT60_SPEC.front_len).rotate([90, 0, 0])

    def section(size: tuple[float, float], start: float, length: float) -> Solid:
        return cube([size[0], length, size[1]]).translate([-size[0] / 2, -start - length, -size[1] / 2])

    # the collar, its two corners on the chamfered (+x) side rounded
    cw, ch, r = *XT60_SPEC.collar, XT60_SPEC.collar_r
    corners = union(*(circle(r=r, fn=32).translate([cw / 2 - r, sz * (ch / 2 - r)]) for sz in (-1, 1)))
    collar_2d = hull(union(square([cw - r, ch]).translate([-cw / 2, -ch / 2]), corners))
    collar = (
        linear_extrude(collar_2d, height=XT60_SPEC.collar_len)
        .rotate([90, 0, 0])
        .translate([0, -XT60_SPEC.front_len, 0])
    )

    collar_end = XT60_SPEC.front_len + XT60_SPEC.collar_len
    rear = collar_end + XT60_SPEC.flange_len
    return union(
        front,
        collar,
        section(XT60_SPEC.flange, collar_end, XT60_SPEC.flange_len),
        section(XT60_SPEC.cap, rear, XT60_SPEC.length - rear),
    ).color("Gold")
