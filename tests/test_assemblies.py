"""Assemblies build, and their parts actually meet: nothing floats in mid-air."""

import pytest
from cadder.handles import get_handle, get_handles, shift_handle
from cadder.hardware import shcs, sk10, vslot_x
from cadder.testing import bounding_box, connected_groups, flatten, touching, volume
from pythonscad import union

from plotzker.assemblies import ASSEMBLIES, baseboard, loom
from plotzker.assemblies.carriage import carriage_assembly, carriage_fit_check
from plotzker.assemblies.gantry import (
    gantry_assembly,
    gantry_end_local,
    gantry_fit_check,
    x_endstop_keepout,
)
from plotzker.assemblies.machine import pen_holder_at
from plotzker.assemblies.pen_holder import pen_holder_assembly, pen_holder_items
from plotzker.assemblies.psu_mount import (
    brackets_local,
    psu_mount_assembly,
    psu_mount_fit_check,
    psu_mount_local,
)
from plotzker.assemblies.skeleton import carriage_x_at, gantry_y_at, moving_parts
from plotzker.assemblies.y_drive import gantry_y_at as y_gantry_y_at
from plotzker.assemblies.y_drive import y_drive_assembly, y_drive_fit_check, y_endstop_keepout
from plotzker.hardware import C14_INLET_SPEC, xt60_female, y_shaft
from plotzker.params import BEAM, CARRIAGE, FRAME, X_DRIVE, Y_AXIS
from plotzker.parts.gantry_end_bracket import Side, gantry_end_bracket_local
from plotzker.parts.psu_hood import psu_hood_installed
from plotzker.parts.x_motor_mount import x_motor_mount_left
from plotzker.parts.y_idler_mount import y_idler_mount_installed
from plotzker.parts.y_motor_mount import y_motor_mount_installed


@pytest.mark.parametrize("name", ASSEMBLIES)
def test_assembly_builds(name):
    assert volume(union(*flatten(ASSEMBLIES[name].build()))) > 0


# The skeleton is left out on purpose: its bed has nothing to sit on until the bed
# supports are designed (T3.7).
@pytest.mark.parametrize(
    "assembly",
    [
        carriage_fit_check,
        lambda: gantry_end_local(Side.LEFT),
        lambda: gantry_end_local(Side.RIGHT),
        gantry_fit_check,
        psu_mount_fit_check,
        lambda: y_drive_fit_check(0),
        lambda: y_drive_fit_check(1),
    ],
    ids=[
        "carriage on the beam",
        "left gantry end",
        "right gantry end",
        "gantry on the shafts",
        "PSU beside the baseboard",
        "Y drive, gantry at the front",
        "Y drive, gantry at the back",
    ],
)
def test_assembly_is_connected(assembly):
    groups = connected_groups(assembly())
    assert len(groups) == 1, f"floating items (indices into the assembly list): {groups[1:]}"


def test_travel_stays_on_the_board():
    for position in (0, 1):
        assert 0 < gantry_y_at(position) < FRAME.board_size[1]
        assert 0 < carriage_x_at(position) < FRAME.board_size[0]


@pytest.mark.parametrize("position", [0, 0.5, 1])
def test_y_drive_clears_the_gantry(position):
    """Nothing of the Y drive collides with the gantry or the SK10s along the whole travel.

    The only contact allowed is the endstop lever being pressed by the trigger screw
    (under 3 mm³ per side at the front end, where the lever is drawn undeflected).
    """
    gantry_y = y_gantry_y_at(position)
    fixed = []
    for x in Y_AXIS.shaft_x:
        fixed.append(y_shaft().translate([x, Y_AXIS.shaft_y0, Y_AXIS.shaft_z]))
        fixed += [sk10().translate([x, y, 0]) for y in Y_AXIS.sk10_y]
    others = union(*flatten(gantry_assembly(gantry_y)), *fixed)
    drive = union(*flatten(y_drive_assembly(gantry_y)))
    assert volume(drive & others) < 2 * 3


@pytest.mark.parametrize("position", [0, 1])
def test_y_endstop_plug_space_is_free(position):
    """A plug can be pushed onto each Y endstop's connector: nothing is in the way."""
    gantry_y = y_gantry_y_at(position)
    solids = [*flatten(y_drive_assembly(gantry_y)), *flatten(gantry_assembly(gantry_y))]
    for side in Side:
        keepout = y_endstop_keepout(side)
        assert all(volume(keepout & s) < 0.1 for s in solids)


def test_x_endstop_plug_space_is_free():
    """A plug can be pushed onto the X endstop's connector: nothing is in the way."""
    keepout = x_endstop_keepout()
    assert all(volume(keepout & s) < 0.1 for s in flatten(gantry_end_local(Side.LEFT)))


@pytest.mark.parametrize(
    ("mount", "sk10_y", "outward"),
    [
        (y_idler_mount_installed, Y_AXIS.sk10_y[0], -1),
        (y_motor_mount_installed, Y_AXIS.sk10_y[1], 1),
    ],
    ids=["idler mount, front SK10", "motor mount, rear SK10"],
)
def test_sk10_seats_in_the_mount_corner(mount, sk10_y, outward):
    """The SK10 rests in the corner of its mount's pocket (end wall + outboard side wall) and
    is free to move toward the open sides."""
    solid = mount()

    def overlap(dx, dy):
        return volume(solid & sk10().translate([dx, sk10_y + dy, 0]))

    assert overlap(0, 0) < 1e-6
    assert touching(solid, sk10().translate([0, sk10_y, 0]))
    assert overlap(-0.3, 0) > 0.1, "the outboard wall must locate the SK10"
    assert overlap(0, 0.3 * outward) > 0.1, "the end wall must locate the SK10"
    assert overlap(0.3, 0) < 1e-6, "the inboard side must be open"
    assert overlap(0, -0.3 * outward) < 1e-6, "the side toward the other SK10 must be open"


def test_pen_holder_is_connected_with_the_pen_up():
    """With the slide lifted, the pin carries it: the whole head hangs together."""
    groups = connected_groups(list(pen_holder_items(pen_up=True).values()))
    assert len(groups) == 1, f"floating items (indices into the assembly list): {groups[1:]}"


# The horn rides on the servo's spline and the pin sits in the horn's hole.
PEN_HOLDER_MATING_PAIRS = {frozenset(("servo", "horn")), frozenset(("horn", "pin"))}


@pytest.mark.parametrize("pen_up", [False, True], ids=["pen down", "pen up"])
@pytest.mark.parametrize("pen_dia", [7, 10, 16])
def test_pen_holder_parts_do_not_collide(pen_up, pen_dia):
    """Nothing overlaps except the horn on its spline and the pin in its hole: the slide
    clears the body and servo wall, and pens of every size clear the rod arms and sleeves."""
    items = list(pen_holder_items(pen_up, pen_dia).items())
    for i, (name_a, a) in enumerate(items):
        for name_b, b in items[i + 1 :]:
            if frozenset((name_a, name_b)) not in PEN_HOLDER_MATING_PAIRS:
                assert volume(a & b) < 0.05, f"{name_a} collides with {name_b}"


@pytest.mark.parametrize("pen_up", [False, True], ids=["pen down", "pen up"])
def test_pen_holder_clears_the_carriage(pen_up):
    """The tool head hangs on the carriage's face without touching wheels, bolts or beam."""
    beam = vslot_x(240, BEAM.size).translate([-120, -BEAM.depth / 2, BEAM.bottom_z])
    carriage = union(*flatten([*carriage_assembly(), beam]))
    assert all(volume(item & carriage) < 0.05 for item in pen_holder_assembly(pen_up))


#: the XT60 is a press fit in the hood: this much of it overlaps the window and pocket
XT60_PRESS_MM3 = 15


def test_psu_mount_parts_do_not_collide():
    """PSU, brackets, hood, inlet, XT60 and screws clear each other (the screws sit in the
    PSU's holes), except the XT60's press fit in the hood."""
    items = list(psu_mount_local())
    hood = 1 + len(brackets_local())
    xt60 = hood + 2 + 2 * len(C14_INLET_SPEC.hole_xy)  # after the inlet, its screws and nuts
    for i, a in enumerate(items):
        for j in range(i + 1, len(items)):
            limit = XT60_PRESS_MM3 if (i, j) == (hood, xt60) else 0.05
            assert volume(a & items[j]) < limit, (i, j)


def test_psu_mount_clears_the_board_runners_and_loom():
    """Nothing of the PSU mount but the wood screws enters the baseboard, and it stays clear
    of the runners and the Y loom (gantry at the front, where the loom lies nearest)."""
    board = baseboard.baseboard()
    others = union(*flatten([*baseboard.runners(), *loom.rails(), *loom.y_loom(y_gantry_y_at(0))]))
    for item in psu_mount_assembly():
        low, high = bounding_box(item)
        is_wood_screw = high[2] - low[2] > 20 and high[0] - low[0] < 10 and high[1] - low[1] < 10
        if not is_wood_screw:
            assert volume(item & board) < 0.05
        assert volume(item & others) < 0.05


def test_xt60_stops_on_the_lip_and_goes_in_one_way_only():
    """Seated, the XT60 clears the hood; pulled out (-z, as when unplugging) its collar meets
    the lip; turned over (180° about its axis) its square corners meet the keyed window."""
    hood = psu_hood_installed()
    seat = get_handle(hood, "xt60")
    plug = xt60_female().align(seat)
    press = volume(plug & hood)
    assert press < XT60_PRESS_MM3  # only the press fit's interference
    assert volume(plug.translate([0, 0, -0.5]) & hood) > press + 1
    assert volume(xt60_female().rotate([0, 180, 0]).align(seat) & hood) > press + 2


# --- the whole machine (T3.7)

#: gantry and carriage at their four corners of travel (front/back, left/right)
TRAVEL_CORNERS = [(g, c) for g in (0, 1) for c in (0, 1)]
CORNER_IDS = ["front left", "front right", "back left", "back right"]


def test_machine_is_connected():
    """Board, runners, shafts and bed hold together with the gantry and carriage on the
    shafts. The pen holder hangs on the carriage with a printing gap, so it is left out."""
    groups = connected_groups(
        [*baseboard.fixed_assembly(), *moving_parts(0.5, 0.5)],
    )
    assert len(groups) == 1, f"floating items (indices into the assembly list): {groups[1:]}"


@pytest.mark.parametrize(("gantry", "carriage"), TRAVEL_CORNERS, ids=CORNER_IDS)
def test_pen_holder_clears_the_machine_at_the_travel_corners(gantry, carriage):
    """The tool head and the pen, up and down, hit nothing with the gantry and carriage at
    the four corners of travel (the carriage's own trigger on the X endstop lever aside)."""
    fixed = union(*flatten([*baseboard.fixed_assembly(), *moving_parts(gantry, carriage)]))
    for pen_up in (False, True):
        head = pen_holder_at(gantry, carriage, pen_up)
        pen = [item for item in head if volume(item & fixed) > 0.05]
        assert len(pen) <= 1, "more than the pen touches the machine"
        if pen_up:
            assert not pen


def test_bed_posts_clear_the_carriage_path():
    """Nothing of the bed posts rises into the height the carriage and tool head sweep."""
    for item in baseboard.bed():
        assert bounding_box(item)[1][2] < CARRIAGE.bottom_z


@pytest.mark.parametrize("gantry", [0, 0.5, 1], ids=["gantry front", "gantry middle", "gantry back"])
def test_y_loom_clears_the_machine(gantry):
    """The loom, along its whole path, touches nothing but the baseboard it lies on: it sits
    in the anchor's groove, outside the belt and rails, and clear of the Y motor mount."""
    others = [*baseboard.fixed_assembly(), *loom.rails(), *moving_parts(gantry, 0.5)]
    for capsule in loom.y_loom(gantry_y_at(gantry)):
        for item in flatten(others):
            assert volume(capsule & item) < 0.5


def test_loom_anchor_is_held_by_its_screws():
    """The anchor block sits on the right bracket and its screws reach the nut slots."""
    right = list(flatten(gantry_end_local(Side.RIGHT)))
    anchor = next(i for i in right if volume(i) > 0 and bounding_box(i)[0][2] > 9.9)
    assert touching(anchor, right[0])


def test_x_motor_screws_clear_the_mount_bolts():
    """T3.11: the motor's M3 heads and the mount's M5 heads must both fit."""
    mount = x_motor_mount_left()
    bracket = gantry_end_bracket_local(Side.RIGHT)
    m3 = [shcs(3, 10).align(h) for h in get_handles(mount, "motor_screws")]
    m5 = [
        shcs(5, 25).align(shift_handle(h, [0, 0, X_DRIVE.foot_thickness - X_DRIVE.foot_head_recess]))
        for h in get_handles(bracket, "block_bolts_rear")
        if h[1][3] < Y_AXIS.scs_pitch / 2
    ]
    assert len(m3) == 4 and len(m5) == 2
    assert volume(union(*m3) & union(*m5)) < 1e-3
    # and the heads sit inside the counterbores
    assert volume(union(*m5) & mount) < 1e-3


def test_x_endstop_board_seats_flat_over_its_solder():
    """T3.14: solder joints stick out up to 1.8 mm under the board; only the lands touch it."""
    from cadder.handles import get_handle
    from pythonscad import cube, cylinder

    from plotzker.hardware import ENDSTOP_SPEC
    from plotzker.params import X_ENDSTOP
    from plotzker.parts.x_endstop_mount import x_endstop_mount_installed

    mount = x_endstop_mount_installed()
    board_bottom = X_ENDSTOP.board_bottom_z - Y_AXIS.scs_top_z
    yc = sum(X_ENDSTOP.board_y) / 2
    solder = cube([ENDSTOP_SPEC.pcb[0] - 2, ENDSTOP_SPEC.pcb[1] - 2, 1.8]).translate(
        [X_ENDSTOP.board_x[0] + 1, X_ENDSTOP.board_y[0] + 1, board_bottom - 1.8]
    )
    lands = [
        cylinder(d=X_ENDSTOP.land_dia + 0.2, h=5, fn=24).translate(
            [X_ENDSTOP.hole_x, yc + s * ENDSTOP_SPEC.hole_pitch / 2, board_bottom - 3]
        )
        for s in (-1, 1)
    ]
    assert get_handle(mount, "board")
    assert volume((solder - union(*lands)) & mount) < 1e-3
    # and the board's underside still rests on the lands
    pad = cylinder(d=X_ENDSTOP.land_dia - 1, h=0.4, fn=24).translate(
        [X_ENDSTOP.hole_x, yc + ENDSTOP_SPEC.hole_pitch / 2, board_bottom - 0.2]
    )
    assert volume(pad & mount) > 1


def test_x_trigger_screw_reaches_through_its_captive_nut():
    """T3.14: the short trigger screw still engages its captive nut with ~3 mm to spare."""
    from cadder.hardware import metric

    from plotzker.params import CARRIAGE

    head_underside = -CARRIAGE.rear_width / 2 - metric(3).nut_height  # end of adjustment, outermost lock nut
    tip = head_underside + CARRIAGE.trigger_screw_length
    nut_far_face = -CARRIAGE.rear_width / 2 + 3.5 + metric(3).nut_height / 2
    assert tip - nut_far_face >= 3


@pytest.mark.parametrize("side", [Side.LEFT, Side.RIGHT])
def test_y_endstop_board_seats_flat_over_its_solder(side):
    """T3.14: same as the X board: only the lands touch the 1.8 mm solder side of the board."""
    from pythonscad import cube, cylinder

    from plotzker.hardware import ENDSTOP_SPEC
    from plotzker.params import Y_ENDSTOP

    mount = y_idler_mount_installed(side)
    zc = Y_ENDSTOP.board_z_center(-1 if side is Side.LEFT else 1)
    solder = cube([1.8, ENDSTOP_SPEC.pcb[0] - 2, ENDSTOP_SPEC.pcb[1] - 2]).translate(
        [Y_ENDSTOP.board_x0 - 1.8, Y_ENDSTOP.board_y[0] + 1, zc - ENDSTOP_SPEC.pcb[1] / 2 + 1]
    )
    lands = [
        cylinder(d=Y_ENDSTOP.land_dia + 0.2, h=5, fn=24)
        .rotate([0, 90, 0])
        .translate(
            [
                Y_ENDSTOP.board_x0 - 3,
                Y_ENDSTOP.board_front_y + ENDSTOP_SPEC.hole_v,
                zc + s * ENDSTOP_SPEC.hole_pitch / 2,
            ]
        )
        for s in (-1, 1)
    ]
    assert volume((solder - union(*lands)) & mount) < 1e-3
    pad = (
        cylinder(d=Y_ENDSTOP.land_dia - 1, h=0.4, fn=24)
        .rotate([0, 90, 0])
        .translate(
            [Y_ENDSTOP.board_x0 - 0.2, Y_ENDSTOP.board_front_y + ENDSTOP_SPEC.hole_v, zc + ENDSTOP_SPEC.hole_pitch / 2]
        )
    )
    assert volume(pad & mount) > 1


@pytest.mark.parametrize("shift", [-1, 0, 1])
def test_x_idler_slider_rides_free_over_its_whole_travel(shift):
    """T3.22: along the whole tension travel the floating slider neither touches the bracket's
    tower (plate and walls, a loose fit) nor the endstop mount, nor reaches into the endstop's
    plug space."""
    from plotzker.params import X_IDLER
    from plotzker.parts.idler_slider import x_idler_slider_installed
    from plotzker.parts.x_endstop_mount import x_endstop_mount_installed

    moved = x_idler_slider_installed().translate([shift * X_IDLER.travel / 2, 0, 0])
    bracket = gantry_end_bracket_local(Side.LEFT)
    assert not touching(moved, bracket)
    assert volume(moved & bracket) < 1e-3
    assert not touching(moved, x_endstop_mount_installed())
    assert volume(moved & x_endstop_keepout()) < 1e-3


@pytest.mark.parametrize("shift", [-1, 0, 1])
def test_x_idler_axle_bolt_and_nut_clear_the_tower_walls(shift):
    """T3.22: the axle bolt's head, its shank's tip and the nut stick out of the slider's arms; over
    the whole travel they touch neither the tower's walls nor anything else of the bracket."""
    from cadder.handles import get_handle, shift_handle
    from cadder.hardware import hex_nut, shcs

    from plotzker.params import X_BELT, X_DRIVE, X_IDLER
    from plotzker.parts.idler_slider import x_idler_slider_installed

    dx = shift * X_IDLER.travel / 2
    axle = shift_handle(get_handle(x_idler_slider_installed(), "axle"), [dx, 0, 0])
    nut = (
        hex_nut(X_IDLER.axle_screw_size)
        .rotate([0, 0, 90])
        .rotate([-90, 0, 0])
        .translate([X_DRIVE.idler_x + dx, X_BELT.y + X_IDLER.nut_seat_y, X_IDLER.axle_z])
    )
    bracket = gantry_end_bracket_local(Side.LEFT)
    for part in (shcs(X_IDLER.axle_screw_size, 25).align(axle), nut):
        assert volume(part & bracket) < 1e-3


@pytest.mark.parametrize("side", [Side.LEFT, Side.RIGHT])
@pytest.mark.parametrize("shift", [-1, 0, 1])
def test_y_idler_slider_rides_free_over_its_whole_travel(side, shift):
    """T3.23: along the whole tension travel the floating slider neither touches its mount (the
    tower's plate and walls, a loose fit) nor reaches into the endstop's plug space or the front
    SK10."""
    from cadder.handles import frame_axes, get_handle, place_in_frame

    from plotzker.hardware import endstop_keepout
    from plotzker.params import Y_IDLER
    from plotzker.parts.idler_slider import y_idler_slider_installed

    moved = y_idler_slider_installed(side).translate([0, shift * Y_IDLER.travel / 2, 0])
    assert not touching(moved, y_idler_mount_installed(side))
    keepout = place_in_frame(
        endstop_keepout(),
        *frame_axes(get_handle(y_idler_mount_installed(side), "board")),
    )
    assert volume(moved & keepout) < 1e-3
    assert volume(moved & sk10().translate([0, Y_AXIS.sk10_y[0], 0])) < 1e-3


@pytest.mark.parametrize("side", [Side.LEFT, Side.RIGHT])
@pytest.mark.parametrize("shift", [-1, 0, 1])
def test_y_idler_axle_bolt_and_nut_clear_the_tower_walls(side, shift):
    """T3.23: the axle bolt's head, its tip and the nut stick out of the slider's arms; over the
    whole travel they touch nothing of the mount."""
    from cadder.handles import get_handle, shift_handle
    from cadder.hardware import hex_nut, metric, shcs

    from plotzker.params import Y_DRIVE
    from plotzker.parts.y_idler_mount import idler_for

    idler = idler_for(side)
    dy = shift * idler.travel / 2
    mount = y_idler_mount_installed(side)
    axle = shift_handle(get_handle(mount, "axle"), [0, dy, 0])
    nut = (
        hex_nut(idler.axle_screw_size)
        .rotate([0, 90 * idler.head_side, 0])
        .translate(
            [
                Y_AXIS.belt_x + idler.head_side * (idler.width / 2 - metric(idler.axle_screw_size).nut_height),
                Y_DRIVE.idler_y + dy,
                idler.axle_z,
            ]
        )
    )
    for part in (shcs(idler.axle_screw_size, idler.axle_length).align(axle), nut):
        assert volume(part & mount) < 1e-3


@pytest.mark.parametrize("which", ["x", "y"])
def test_floating_slider_arm_ends_have_a_straight_45_degree_top_front(which):
    """T3.22: printed upside down the arms' round ends must not droop: the top front corner is a
    straight 45° line, so material is solid just below it and absent just above it."""
    from pythonscad import cube

    from plotzker.params import X_IDLER, Y_IDLER
    from plotzker.parts.floating_idler import slider_local

    idler = X_IDLER if which == "x" else Y_IDLER
    slider = slider_local(idler)
    y_mid = idler.gap_y / 2 + idler.arm_thickness / 2
    x = idler.chamfer_x + 1.0  # past the start of the line
    line_z = idler.arm_top - 1.0  # the 45° line's height there

    def probe(dz: float):
        return cube([0.4, 1, 0.4]).translate([x - 0.2, y_mid - 0.5, line_z + dz - 0.2])

    assert volume(slider & probe(-0.8)) > 0.9 * 0.4 * 0.4 * 1  # solid below the line
    assert volume(slider & probe(+0.8)) < 1e-3  # nothing above it
