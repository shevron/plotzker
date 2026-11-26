"""The machine as a FreeCAD assembly (``freecad/PenPlotter.FCStd``, see ``freecad/README.md``).

Cuts the same solid model that ``assemblies/machine.py`` draws into named components (printed
parts, purchased parts, grouped fasteners), each placed in the machine frame at the reference
pose (gantry and carriage at mid-travel, pen up), in four rigid bodies (base, gantry, carriage,
pen slide), with the joints that give the machine its motion (all numbers from ``params``).
cadder exports and builds it: ``python -m plotzker freecad``.
"""

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING, Any

from cadder.freecad import Body, Components, FreeCadAssembly, Joint
from cadder.handles import get_handles
from cadder.hardware import vslot_x
from pythonscad import translate

from plotzker import params
from plotzker.assemblies import baseboard
from plotzker.assemblies.carriage import carriage_assembly
from plotzker.assemblies.gantry import gantry_end_local
from plotzker.assemblies.pen_holder import pen_holder_items
from plotzker.assemblies.psu_mount import brackets_local, hood_local, placed
from plotzker.assemblies.skeleton import carriage_x_at, gantry_y_at
from plotzker.assemblies.y_drive import (
    y_belt_runs,
    y_endstop_board,
    y_idler_end_local,
    y_motor_end_local,
)
from plotzker.hardware import C14_INLET_SPEC, PSU_SPEC, psu
from plotzker.params import (
    BEAM,
    BRACKET,
    CARRIAGE,
    FRAME,
    PEN,
    X_BELT,
    X_DRIVE,
    Y_AXIS,
    Y_DRIVE,
)
from plotzker.parts import gantry_end_bracket
from plotzker.parts.x_carriage import WHEEL_X
from plotzker.types import Side

if TYPE_CHECKING:
    from pythonscad import Solid


#: Reference pose of the export: fractions of the gantry and carriage travel, pen lifted.
GANTRY_POS = 0.5
CARRIAGE_POS = 0.5

# Display colors (RGB 0..255) by kind of component.
PRINTED = (255, 140, 0)
PRINTED_PEN = (70, 130, 180)
WOOD = (222, 184, 135)
BED = (210, 180, 140)
STEEL = (112, 128, 144)
ALU = (190, 190, 195)
SILVER = (210, 210, 215)
MOTOR = (60, 60, 65)
DARK = (30, 30, 30)
FASTENER = (150, 150, 155)
GOLD = (218, 165, 32)
GREEN = (60, 179, 113)
RED = (220, 20, 60)
BOARD = (0, 100, 60)


def _mirror_x(items: list[Solid], x: float) -> list[Solid]:
    """Mirror items about x = 0, then move them by ``x`` (the right side of a symmetric pair)."""
    return [translate(item.mirror([1, 0, 0]), [x, 0, 0]) for item in items]


def _shift(items: list[Solid], offset: list[float]) -> list[Solid]:
    return [translate(item, offset) for item in items]


def _fixed_parts(components: Components) -> None:
    """Baseboard and everything screwed to it."""
    board_assembly = baseboard
    items = board_assembly.fixed_assembly()
    components.add("baseboard", board_assembly.baseboard(), "base", WOOD, transparency=60)

    runners = board_assembly.runners()
    per_runner = 1 + 2 * len(params.BASEBOARD.runner_screw_x)
    assert len(runners) == per_runner * len(params.BASEBOARD.runner_y)
    for i in range(len(params.BASEBOARD.runner_y)):
        components.add(f"runner_{i}", runners[i * per_runner], "base", ALU, shape="vslot_2040")
    components.add(
        "runner_fasteners",
        [s for i, s in enumerate(runners) if i % per_runner],
        "base",
        FASTENER,
    )

    shafts = board_assembly.shafts_and_supports()
    per_shaft = 1 + len(Y_AXIS.sk10_y) * (1 + 4 * len(params.BASEBOARD.sk10_hole_x))
    assert len(shafts) == 2 * per_shaft
    fasteners: list[Solid] = []
    for side, label in enumerate("LR"):
        chunk = shafts[side * per_shaft : (side + 1) * per_shaft]
        components.add(f"y_shaft_{label}", chunk[0], "base", SILVER)
        step = 1 + 4 * len(params.BASEBOARD.sk10_hole_x)
        for j in range(len(Y_AXIS.sk10_y)):
            block = chunk[1 + j * step : 1 + (j + 1) * step]
            components.add(f"sk10_{label}{j}", block[0], "base", STEEL)
            fasteners += block[1:]
    components.add("sk10_fasteners", fasteners, "base", FASTENER)

    bed = board_assembly.bed()
    components.add("bed_panel", bed[0], "base", BED, transparency=60)
    components.add("bed_steel", bed[1], "base", STEEL)
    components.add("bed_posts", bed[2:], "base", FASTENER)

    n_psu = _psu_parts(components)
    assert len(items) == 1 + len(runners) + len(shafts) + len(bed) + n_psu


def _psu_parts(components: Components) -> int:
    """The PSU, its brackets and its hood with the inlet and the XT60; returns the number of
    solids (as in ``psu_mount.psu_mount_assembly``)."""
    components.add("psu", placed(psu()), "base", SILVER)
    brackets = [placed(item) for item in brackets_local()]
    per_bracket = 1 + len(PSU_SPEC.bottom_hole_x) + len(params.PSU_MOUNT.wood_screw_z)
    assert len(brackets) == per_bracket * len(PSU_SPEC.hole_y)
    for i in range(len(PSU_SPEC.hole_y)):
        components.add(f"psu_bracket_{i}", brackets[i * per_bracket], "base", PRINTED_PEN)
    # hood_local: hood, inlet, inlet screws, inlet nuts, XT60, hood screws
    hood = [placed(item) for item in hood_local()]
    xt60 = 2 + 2 * len(C14_INLET_SPEC.hole_xy)
    components.add("psu_hood", hood[0], "base", PRINTED)
    components.add("c14_inlet", hood[1], "base", DARK)
    components.add("xt60", hood[xt60], "base", GOLD)
    components.add(
        "psu_fasteners",
        [s for i, s in enumerate(brackets) if i % per_bracket]
        + [s for i, s in enumerate(hood) if i not in (0, 1, xt60)],
        "base",
        FASTENER,
    )
    return 1 + len(brackets) + len(hood)


def _place_side(items: list[Solid], x: float, mirrored: bool) -> list[Solid]:
    """Items of a left-hand end moved to the shaft at ``x``, mirrored for the right-hand one."""
    return _mirror_x(items, x) if mirrored else _shift(items, [x, 0, 0])


def _y_drive_parts(components: Components, gantry_y: float) -> None:
    """Y motor and idler ends, endstops and the static lower belt run on each side."""
    sides = ((Side.LEFT, "L", Y_AXIS.shaft_x[0], False), (Side.RIGHT, "R", Y_AXIS.shaft_x[1], True))
    for side, label, shaft_x, mirrored in sides:
        idler = y_idler_end_local(side)
        motor = y_motor_end_local()
        runs = y_belt_runs(gantry_y)

        place = partial(_place_side, x=shaft_x, mirrored=mirrored)

        i = place(idler)
        placed_motor = place(motor)
        components.add(f"y_idler_mount_{label}", i[0], "base", PRINTED)
        components.add(f"y_idler_slider_{label}", i[1], "base", PRINTED)
        components.add(f"y_idler_{label}", i[2], "base", ALU, shape="gt2_idler")
        components.add(f"y_idler_fasteners_{label}", i[3:], "base", FASTENER)
        components.add(f"y_motor_mount_{label}", placed_motor[0], "base", PRINTED)
        components.add(f"y_motor_{label}", placed_motor[1], "base", MOTOR, shape="nema17")
        components.add(f"y_pulley_{label}", placed_motor[2], "base", SILVER, shape="gt2_pulley")
        components.add(f"y_motor_screws_{label}", placed_motor[3:], "base", FASTENER)
        components.add(f"y_belt_lower_{label}", place(runs[:1])[0], "base", DARK)
        components.add(f"y_endstop_{label}", y_endstop_board(side), "base", BOARD, shape="endstop_board")


def _gantry_parts(components: Components, gantry_y: float) -> None:
    """Both gantry ends, the beam, and the X belt's upper run."""
    left_x, right_x = Y_AXIS.shaft_x
    n_front = len(get_handles(gantry_end_bracket.gantry_end_bracket(Side.LEFT), "block_bolts_front"))
    n_rear = len(get_handles(gantry_end_bracket.gantry_end_bracket(Side.LEFT), "block_bolts_rear"))
    n_beam = len(get_handles(gantry_end_bracket.gantry_end_bracket(Side.LEFT), "beam_bolts"))
    n_clamps = len(get_handles(gantry_end_bracket.gantry_end_bracket(Side.LEFT), "belt_clamps"))

    for side, label, shaft_x, mirrored, n_drive in (
        (Side.LEFT, "L", left_x, False, 8),
        (Side.RIGHT, "R", right_x, True, 3),
    ):
        local = gantry_end_local(side)
        origin = [0, gantry_y, Y_AXIS.scs_top_z]
        items = [translate(item, origin) for item in local]
        items = _mirror_x(items, shaft_x) if mirrored else _shift(items, [shaft_x, 0, 0])
        cursor = 0

        def take(count: int, items: list[Solid] = items) -> list[Solid]:
            nonlocal cursor
            chunk = items[cursor : cursor + count]
            cursor += count
            return chunk

        components.add(f"gantry_bracket_{label}", take(1)[0], "gantry", PRINTED)
        blocks = take(2)
        components.add(f"scs10uu_{label}0", blocks[0], "gantry", STEEL)
        components.add(f"scs10uu_{label}1", blocks[1], "gantry", STEEL)
        fasteners = take(n_front + n_rear)
        drive = take(n_drive)
        fasteners += take(n_beam)
        clamps = take(2 * n_clamps)
        fasteners += take(1)  # endstop trigger screw
        anchor: list[Solid] = []
        if side is Side.RIGHT:  # the Y loom anchor block and its screws
            anchor = take(1)
            fasteners += take(len(items) - cursor)
        assert cursor == len(items), (cursor, len(items))
        components.add(f"gantry_fasteners_{label}", fasteners, "gantry", FASTENER)
        if anchor:
            components.add("loom_anchor", anchor[0], "gantry", PRINTED)
        components.add(f"y_belt_clamps_{label}", clamps[0::2], "gantry", GOLD)
        components.add(f"y_belt_clamped_{label}", clamps[1::2], "gantry", DARK)
        names: tuple[str, ...]
        colors: tuple[tuple[int, int, int], ...]
        if side is Side.LEFT:
            names = (
                "x_endstop_mount",
                "x_idler_slider",
                "x_idler",
                "x_idler_bolt",
                "x_idler_nut",
                "x_idler_tension_screw",
                "x_idler_tension_nut",
                "x_endstop",
            )
            colors = (PRINTED, PRINTED, ALU, FASTENER, FASTENER, FASTENER, FASTENER, BOARD)
        else:
            names = ("x_motor_mount", "x_motor", "x_pulley")
            colors = (PRINTED, MOTOR, SILVER)
        for name, solid, color in zip(names, drive, colors, strict=True):
            components.add(name, solid, "gantry", color)

    belt = _x_belt_return(gantry_y)
    components.add("x_belt_upper", belt, "gantry", DARK)
    beam = vslot_x(BEAM.length, BEAM.size).translate(
        [left_x + BEAM.end_offset, gantry_y - BEAM.depth / 2, BEAM.bottom_z]
    )
    components.add("gantry_beam", beam, "gantry", ALU)


def _x_belt_return(gantry_y: float) -> Solid:
    """The X belt's upper (free) run, as ``gantry_assembly`` draws it."""
    from cadder.hardware import GT2_SPEC, PULLEY_SPEC
    from pythonscad import cube

    left_x, _ = Y_AXIS.shaft_x
    return cube(
        [Y_AXIS.shaft_spacing - X_DRIVE.idler_x - X_DRIVE.motor_x, GT2_SPEC.width, GT2_SPEC.thickness]
    ).translate(
        [
            left_x + X_DRIVE.idler_x,
            gantry_y + X_BELT.y - GT2_SPEC.width / 2,
            X_BELT.pulley_axis_z + PULLEY_SPEC.pitch_dia / 2 - GT2_SPEC.pitch_line_from_back,
        ]
    )


def _place_head(solid: Solid, carriage_x: float, gantry_y: float) -> Solid:
    """A pen holder item, turned to the carriage's front face at the carriage's position."""
    turned = solid.mirror([0, 1, 0]).translate([0, CARRIAGE.plate_front_y, 0])
    return translate(turned, [carriage_x, gantry_y, 0])


def _carriage_parts(components: Components, gantry_y: float, carriage_x: float) -> None:
    """X carriage with wheels, fasteners and the pen holder."""
    items = _shift(carriage_assembly(), [carriage_x, gantry_y, 0])
    assert len(items) == 17
    components.add("x_carriage", items[0], "carriage", GREEN)
    fasteners: list[Solid] = []
    for k, label in enumerate(("L", "R")):
        chunk = items[1 + 5 * k : 6 + 5 * k]
        components.add(f"vwheel_{label}_top", chunk[0], "carriage", (40, 40, 40))
        components.add(f"vwheel_{label}_bottom", chunk[2], "carriage", (40, 40, 40))
        fasteners += [chunk[1], chunk[3], chunk[4]]
    components.add("carriage_fasteners", fasteners, "carriage", FASTENER)
    components.add("x_belt_clamps", [items[11], items[13]], "carriage", GOLD)
    components.add("x_belt_clamped", [items[12], items[14]], "carriage", DARK)
    components.add("x_trigger", items[15:17], "carriage", FASTENER)

    head = pen_holder_items(pen_up=True)

    place = partial(_place_head, carriage_x=carriage_x, gantry_y=gantry_y)

    components.add("pen_body", place(head["body"]), "carriage", PRINTED_PEN)
    components.add("pen_servo", place(head["servo"]), "carriage", MOTOR)
    components.add(
        "pen_clamp_screws",
        [place(head["clamp_screw_0"]), place(head["clamp_screw_1"])],
        "carriage",
        FASTENER,
    )
    components.add("pen_horn", [place(head["horn"]), place(head["pin"])], "carriage", SILVER)
    components.add("pen_slide", place(head["slide"]), "slide", PRINTED)
    components.add("pen_rod", place(head["rod"]), "slide", SILVER)
    components.add("pen", place(head["pen"]), "slide", RED)
    components.add(
        "pen_thumbscrew",
        [place(head["thumbscrew"]), place(head["thumbscrew_nut"])],
        "slide",
        FASTENER,
    )


def _axes(gantry_y: float, carriage_x: float) -> dict[str, Any]:
    """Joint frames: ``origin`` in the machine frame at the reference pose, ``dir`` the axis."""
    left_x, right_x = Y_AXIS.shaft_x
    belt_x = Y_AXIS.belt_x
    beam_z = BEAM.bottom_z + BEAM.height / 2
    horn_y = carriage_x, gantry_y + CARRIAGE.plate_front_y - PEN.horn_dia[0]
    axes: dict[str, Any] = {
        "y_shaft_L": {"origin": [left_x, gantry_y, Y_AXIS.shaft_z], "dir": [0, 1, 0]},
        "y_shaft_R": {"origin": [right_x, gantry_y, Y_AXIS.shaft_z], "dir": [0, 1, 0]},
        "beam": {"origin": [carriage_x, gantry_y, beam_z], "dir": [1, 0, 0]},
        "y_idler_L": {
            "origin": [left_x + belt_x, Y_DRIVE.idler_y, Y_AXIS.pulley_axis_z],
            "dir": [1, 0, 0],
        },
        "y_idler_R": {
            "origin": [right_x - belt_x, Y_DRIVE.idler_y, Y_AXIS.pulley_axis_z],
            "dir": [1, 0, 0],
        },
        "y_pulley_L": {
            "origin": [left_x + belt_x, Y_DRIVE.motor_y, Y_AXIS.pulley_axis_z],
            "dir": [1, 0, 0],
        },
        "y_pulley_R": {
            "origin": [right_x - belt_x, Y_DRIVE.motor_y, Y_AXIS.pulley_axis_z],
            "dir": [1, 0, 0],
        },
        "x_idler": {
            "origin": [left_x + X_DRIVE.idler_x, gantry_y + X_BELT.y, X_BELT.pulley_axis_z],
            "dir": [0, 1, 0],
        },
        "x_pulley": {
            "origin": [right_x - X_DRIVE.motor_x, gantry_y + X_BELT.y, X_BELT.pulley_axis_z],
            "dir": [0, 1, 0],
        },
        "pen_horn": {"origin": [carriage_x + PEN.servo_x, horn_y[1], PEN.shaft_z], "dir": [0, 1, 0]},
        "pen_slide": {
            "origin": [carriage_x + PEN.pen_x, gantry_y + CARRIAGE.plate_front_y, 0],
            "dir": [0, 0, 1],
        },
    }
    for k, label in enumerate("LR"):
        sign = -1 if k == 0 else 1
        for z, pos in zip(CARRIAGE.wheel_z, ("top", "bottom"), strict=True):
            axes[f"vwheel_{label}_{pos}"] = {
                "origin": [carriage_x + sign * WHEEL_X, gantry_y, z],
                "dir": [0, 1, 0],
            }
    return axes


def build_components() -> Components:
    """The machine's components at the reference pose."""
    params.check_design()
    gantry_y = gantry_y_at(GANTRY_POS)
    carriage_x = carriage_x_at(CARRIAGE_POS)
    collected = Components()
    _fixed_parts(collected)
    _y_drive_parts(collected, gantry_y)
    _gantry_parts(collected, gantry_y)
    _carriage_parts(collected, gantry_y, carriage_x)
    return collected


def _joint(
    axes: Mapping[str, Mapping[str, Any]], kind: str, a: str, b: str, axis: str, label: str, **kw: Any
) -> Joint:
    """A joint between ``a`` and ``b`` about the named axis."""
    return Joint(kind, a, b, tuple(axes[axis]["origin"]), tuple(axes[axis]["dir"]), label, **kw)  # type: ignore[arg-type]


def joints() -> list[Joint]:
    """The joints that give the machine its motion; travel limits from the reference pose."""
    gantry_y = gantry_y_at(GANTRY_POS)
    carriage_x = carriage_x_at(CARRIAGE_POS)
    axes = _axes(gantry_y, carriage_x)

    joint = partial(_joint, axes)

    y_lo, y_hi = Y_AXIS.gantry_y_range
    x_lo, x_hi = CARRIAGE.center_x_range
    found = [
        # Gantry on the Y shafts: one Slider (along Y) on the left shaft. The right blocks are
        # Fixed to the gantry; a second joint on the right shaft would close a loop (shaft -
        # block - gantry - block - shaft - baseboard) and over-constrain the solver, which then
        # rejects dragging ("a grounded object moved").
        joint(
            "Slider",
            "y_shaft_L",
            "scs10uu_L0",
            "y_shaft_L",
            "Gantry slides on Y shaft (Y)",
            limits=(y_lo - gantry_y, y_hi - gantry_y),
        ),
        joint(
            "Slider",
            "gantry_beam",
            "x_carriage",
            "beam",
            "Carriage slides on beam (X)",
            limits=(x_lo - carriage_x, x_hi - carriage_x),
        ),
        # pen up at the reference pose, so it can only go down
        joint("Slider", "pen_body", "pen_slide", "pen_slide", "Pen slide (Z)", limits=(-PEN.lift, 0.0)),
    ]
    for side in "LR":
        found += [
            joint(
                "Revolute",
                f"y_idler_slider_{side}",
                f"y_idler_{side}",
                f"y_idler_{side}",
                f"Y idler {side} turns",
            ),
            joint(
                "Revolute",
                f"y_motor_{side}",
                f"y_pulley_{side}",
                f"y_pulley_{side}",
                f"Y pulley {side} turns",
            ),
        ]
    found += [
        # the idler turns on the (floating) slider, T3.22
        joint("Revolute", "x_idler_slider", "x_idler", "x_idler", "X idler turns"),
        joint("Revolute", "x_motor", "x_pulley", "x_pulley", "X pulley turns"),
        joint("Revolute", "pen_servo", "pen_horn", "pen_horn", "Servo horn turns"),
    ]
    for side in "LR":
        for pos in ("top", "bottom"):
            found.append(
                joint(
                    "Revolute",
                    "x_carriage",
                    f"vwheel_{side}_{pos}",
                    f"vwheel_{side}_{pos}",
                    f"V-wheel {side} {pos} turns",
                )
            )
    return found


def metadata() -> dict[str, object]:
    """Reference pose and travel, for whoever reads the manifest."""
    return {
        "reference_pose": {
            "gantry_y": gantry_y_at(GANTRY_POS),
            "carriage_x": carriage_x_at(CARRIAGE_POS),
            "pen": "up",
        },
        "travel": {
            "gantry_y": list(Y_AXIS.gantry_y_range),
            "carriage_x": list(CARRIAGE.center_x_range),
            "pen_lift": PEN.lift,
        },
        "frame": {"board": list(FRAME.board_size), "bracket_len_y": BRACKET.length_y},
    }


#: The whole machine, at mid-travel with the pen up
PEN_PLOTTER = FreeCadAssembly(
    name="PenPlotter",
    label="Pen plotter",
    description="The machine at mid-travel, pen up: four rigid bodies and their joints",
    components=build_components,
    bodies=(
        Body("base", "baseboard", grounded=True),
        Body("gantry", "gantry_beam"),
        Body("carriage", "x_carriage"),
        Body("slide", "pen_slide"),
    ),
    joints=joints,
    metadata=metadata,
)
