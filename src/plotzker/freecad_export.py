"""Export the machine as individual components for the FreeCAD assembly (``freecad/``).

Cuts the same solid model that ``assemblies/machine.py`` draws into named components (printed
parts, purchased parts, grouped fasteners), each placed in the machine frame at the reference
pose (gantry and carriage at mid-travel, pen up). Writes ``freecad/stl/<name>.stl`` and
``freecad/components.json``: the component list (rigid body, color) and the joint axes (all
numbers come from ``params``). ``freecad/build_assembly.py`` turns them into the FreeCAD
Assembly with its joints.

Usage: ``python -m plotzker freecad``.
"""

import itertools
import json
import re
import tempfile
from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from pythonscad import export, translate

from plotzker import params
from plotzker.assemblies import baseboard
from plotzker.assemblies.carriage import carriage_assembly
from plotzker.assemblies.gantry import gantry_end_local
from plotzker.assemblies.pen_holder import pen_holder_items
from plotzker.assemblies.skeleton import carriage_x_at, gantry_y_at
from plotzker.assemblies.y_drive import (
    y_belt_runs,
    y_endstop_board,
    y_idler_end_local,
    y_motor_end_local,
)
from plotzker.geometry import get_handles
from plotzker.hardware import vslot_x
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

REPO_ROOT = Path(__file__).resolve().parents[2]
FREECAD_DIR = REPO_ROOT / "freecad"

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


class Exporter:
    """Collects components (name, solid, rigid body, color) and writes them out."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self.solids: dict[str, Solid] = {}

    def add(
        self, name: str, solid: Solid | list[Solid], body: str, color: tuple[int, int, int]
    ) -> None:
        """Register one component; a list of solids (fasteners) is united into one."""
        assert name not in self.solids, name
        if isinstance(solid, list):
            solid = reduce(lambda a, b: a | b, solid)
        self.solids[name] = solid
        self.entries.append({"name": name, "body": body, "color": list(color)})

    def write(self, out_dir: Path) -> None:
        """Write one STL per distinct shape; set each entry's ``stl``, ``center``, ``rotation``.

        Components that are the same shape in another place or orientation (V-wheels, SK10s,
        motors, ...) share one STL: each entry gets the placement (``rotation`` matrix about
        the bounding-box ``center``) that takes the shared mesh to that component's place.
        """
        stl_dir = out_dir / "stl"
        stl_dir.mkdir(parents=True, exist_ok=True)
        for old in stl_dir.glob("*.stl"):
            old.unlink()
        with tempfile.TemporaryDirectory() as tmp:
            shapes = {}
            for name, solid in self.solids.items():
                path = Path(tmp) / f"{name}.stl"
                export(solid, str(path))
                shapes[name] = _Shape.read(path)
            groups = _congruent_groups(shapes)
            for members in groups:
                master = members[0]
                stl_name = _master_name([name for name, _ in members])
                text = (Path(tmp) / f"{master[0]}.stl").read_text()
                (stl_dir / f"{stl_name}.stl").write_text(text)
                for name, rotation in members:
                    entry = next(e for e in self.entries if e["name"] == name)
                    entry["stl"] = stl_name
                    entry["center"] = list(shapes[name].center)
                    entry["rotation"] = [v for row in rotation for v in row]
                shared = f" (x{len(members)}: {', '.join(n for n, _ in members)})"
                typer.echo(f"wrote {stl_name}.stl" + (shared if len(members) > 1 else ""))


#: The 24 proper rotations that map the axes onto themselves (as integer matrices).
def _rotations() -> list[tuple[tuple[int, ...], ...]]:
    found = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            rows = tuple(tuple(signs[r] if perm[r] == c else 0 for c in range(3)) for r in range(3))
            det = (
                rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
                - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
                + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
            )
            if det == 1:
                found.append(rows)
    return found


_ROTATIONS = _rotations()
_IDENTITY = _ROTATIONS[[r == ((1, 0, 0), (0, 1, 0), (0, 0, 1)) for r in _ROTATIONS].index(True)]
_TOL = 0.02  #: mm; two points closer than this are the same vertex


class _Shape:
    """Vertex cloud of an STL, centered on its bounding box."""

    def __init__(self, points: list[tuple[float, float, float]], facets: int) -> None:
        self.facets = facets
        lo = [min(p[k] for p in points) for k in range(3)]
        hi = [max(p[k] for p in points) for k in range(3)]
        self.center = tuple((a + b) / 2 for a, b in zip(lo, hi, strict=True))
        self.extents = tuple(round(b - a, 2) for a, b in zip(lo, hi, strict=True))
        self.points = [
            (p[0] - self.center[0], p[1] - self.center[1], p[2] - self.center[2]) for p in points
        ]
        self.signature = (len(points), facets, tuple(sorted(self.extents)))

    @classmethod
    def read(cls, path: Path) -> _Shape:
        """Parse an ASCII STL."""
        vertices = [
            tuple(float(v) for v in line.split()[1:4])
            for line in path.read_text().splitlines()
            if line.lstrip().startswith("vertex")
        ]
        unique = list({(round(x, 3), round(y, 3), round(z, 3)) for x, y, z in vertices})
        return cls(unique, len(vertices) // 3)

    def maps_to(self, other: _Shape, rotation: tuple[tuple[int, ...], ...]) -> bool:
        """Whether ``other`` is this shape, rotated about the centers, point for point."""
        cell = 4 * _TOL
        grid: dict[tuple[int, int, int], list[tuple[float, float, float]]] = {}
        for p in other.points:
            grid.setdefault(
                (round(p[0] / cell), round(p[1] / cell), round(p[2] / cell)), []
            ).append(p)
        for x, y, z in self.points:
            q = tuple(r[0] * x + r[1] * y + r[2] * z for r in rotation)
            key = (round(q[0] / cell), round(q[1] / cell), round(q[2] / cell))
            if not any(
                abs(c[0] - q[0]) < _TOL and abs(c[1] - q[1]) < _TOL and abs(c[2] - q[2]) < _TOL
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                for dz in (-1, 0, 1)
                for c in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ())
            ):
                return False
        return True


def _congruent_groups(
    shapes: dict[str, _Shape],
) -> list[list[tuple[str, tuple[tuple[int, ...], ...]]]]:
    """Group components that are the same shape (rotation + translation, no mirroring).

    Each group is ``[(name, rotation)]`` with the first member as the master (identity)."""
    groups: list[list[tuple[str, tuple[tuple[int, ...], ...]]]] = []
    for name, shape in shapes.items():
        for group in groups:
            master = shapes[group[0][0]]
            if master.signature != shape.signature:
                continue
            rotation = next((r for r in _ROTATIONS if master.maps_to(shape, r)), None)
            if rotation is not None:
                group.append((name, rotation))
                break
        else:
            groups.append([(name, _IDENTITY)])
    return groups


#: Shared-STL names where the members' own names do not agree on one.
_SHARED_NAMES = {
    "y_motor": "nema17",
    "y_pulley": "gt2_pulley",
    "y_idler": "gt2_idler",
    "y_endstop": "endstop_board",
    "runner": "vslot_2040",  # the runners and the gantry beam
}


def _master_name(names: list[str]) -> str:
    """STL name for a group: the first member's name without side / position suffix."""
    if len(names) == 1:
        return names[0]
    base = re.sub(r"(_[LR])?(_(top|bottom))?(_?\d+)?$", "", names[0])
    return _SHARED_NAMES.get(base, base)


def _mirror_x(items: list[Solid], x: float) -> list[Solid]:
    """Mirror items about x = 0, then move them by ``x`` (the right side of a symmetric pair)."""
    return [translate(item.mirror([1, 0, 0]), [x, 0, 0]) for item in items]


def _shift(items: list[Solid], offset: list[float]) -> list[Solid]:
    return [translate(item, offset) for item in items]


def _fixed_parts(ex: Exporter) -> None:
    """Baseboard and everything screwed to it."""
    bb = baseboard
    items = bb.fixed_assembly()
    ex.add("baseboard", bb.baseboard(), "base", WOOD)

    runners = bb.runners()
    per_runner = 1 + 2 * len(params.BASEBOARD.runner_screw_x)
    assert len(runners) == per_runner * len(params.BASEBOARD.runner_y)
    for i in range(len(params.BASEBOARD.runner_y)):
        ex.add(f"runner_{i}", runners[i * per_runner], "base", ALU)
    ex.add(
        "runner_fasteners",
        [s for i, s in enumerate(runners) if i % per_runner],
        "base",
        FASTENER,
    )

    shafts = bb.shafts_and_supports()
    per_shaft = 1 + len(Y_AXIS.sk10_y) * (1 + 4 * len(params.BASEBOARD.sk10_hole_x))
    assert len(shafts) == 2 * per_shaft
    fasteners: list[Solid] = []
    for side, label in enumerate("LR"):
        chunk = shafts[side * per_shaft : (side + 1) * per_shaft]
        ex.add(f"y_shaft_{label}", chunk[0], "base", SILVER)
        step = 1 + 4 * len(params.BASEBOARD.sk10_hole_x)
        for j in range(len(Y_AXIS.sk10_y)):
            block = chunk[1 + j * step : 1 + (j + 1) * step]
            ex.add(f"sk10_{label}{j}", block[0], "base", STEEL)
            fasteners += block[1:]
    ex.add("sk10_fasteners", fasteners, "base", FASTENER)

    bed = bb.bed()
    ex.add("bed_panel", bed[0], "base", BED)
    ex.add("bed_steel", bed[1], "base", STEEL)
    ex.add("bed_posts", bed[2:], "base", FASTENER)

    zrib = bb.zrib()
    assert len(zrib) == 25
    ex.add("zrib_hanger_0", zrib[0], "base", PRINTED_PEN)
    ex.add("zrib_hanger_1", zrib[1], "base", PRINTED_PEN)
    ex.add("zrib_board", zrib[2], "base", BOARD)
    ex.add("zrib_guard_0", zrib[13], "base", PRINTED)
    ex.add("zrib_guard_1", zrib[24], "base", PRINTED)
    ex.add(
        "zrib_fasteners",
        [s for i, s in enumerate(zrib) if i >= 3 and i not in (13, 24)],
        "base",
        FASTENER,
    )
    assert len(items) == 1 + len(runners) + len(shafts) + len(bed) + len(zrib)


def _y_drive_parts(ex: Exporter, gantry_y: float) -> None:
    """Y motor and idler ends, endstops and the static lower belt run on each side."""
    sides = ((Side.LEFT, "L", Y_AXIS.shaft_x[0], False), (Side.RIGHT, "R", Y_AXIS.shaft_x[1], True))
    for side, label, shaft_x, mirrored in sides:
        idler = y_idler_end_local(side)
        motor = y_motor_end_local()
        runs = y_belt_runs(gantry_y)

        def place(items: list[Solid], x: float = shaft_x, flip: bool = mirrored) -> list[Solid]:
            return _mirror_x(items, x) if flip else _shift(items, [x, 0, 0])

        i = place(idler)
        m = place(motor)
        ex.add(f"y_idler_mount_{label}", i[0], "base", PRINTED)
        ex.add(f"y_idler_slider_{label}", i[1], "base", PRINTED)
        ex.add(f"y_idler_{label}", i[2], "base", ALU)
        ex.add(f"y_idler_fasteners_{label}", i[3:], "base", FASTENER)
        ex.add(f"y_motor_mount_{label}", m[0], "base", PRINTED)
        ex.add(f"y_motor_{label}", m[1], "base", MOTOR)
        ex.add(f"y_pulley_{label}", m[2], "base", SILVER)
        ex.add(f"y_motor_screws_{label}", m[3:], "base", FASTENER)
        ex.add(f"y_belt_lower_{label}", place(runs[:1])[0], "base", DARK)
        ex.add(f"y_endstop_{label}", y_endstop_board(side), "base", BOARD)


def _gantry_parts(ex: Exporter, gantry_y: float) -> None:
    """Both gantry ends, the beam, and the X belt's upper run."""
    left_x, right_x = Y_AXIS.shaft_x
    n_front = len(
        get_handles(gantry_end_bracket.gantry_end_bracket(Side.LEFT), "block_bolts_front")
    )
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

        def take(n: int, items: list[Solid] = items) -> list[Solid]:
            nonlocal cursor
            chunk = items[cursor : cursor + n]
            cursor += n
            return chunk

        ex.add(f"gantry_bracket_{label}", take(1)[0], "gantry", PRINTED)
        blocks = take(2)
        ex.add(f"scs10uu_{label}0", blocks[0], "gantry", STEEL)
        ex.add(f"scs10uu_{label}1", blocks[1], "gantry", STEEL)
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
        ex.add(f"gantry_fasteners_{label}", fasteners, "gantry", FASTENER)
        if anchor:
            ex.add("loom_anchor", anchor[0], "gantry", PRINTED)
        ex.add(f"y_belt_clamps_{label}", clamps[0::2], "gantry", GOLD)
        ex.add(f"y_belt_clamped_{label}", clamps[1::2], "gantry", DARK)
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
            ex.add(name, solid, "gantry", color)

    belt = _x_belt_return(gantry_y)
    ex.add("x_belt_upper", belt, "gantry", DARK)
    beam = vslot_x(BEAM.length, BEAM.size).translate(
        [left_x + BEAM.end_offset, gantry_y - BEAM.depth / 2, BEAM.bottom_z]
    )
    ex.add("gantry_beam", beam, "gantry", ALU)


def _x_belt_return(gantry_y: float) -> Solid:
    """The X belt's upper (free) run, as ``gantry_assembly`` draws it."""
    from pythonscad import cube

    from plotzker.hardware import GT2, PULLEY

    left_x, _ = Y_AXIS.shaft_x
    return cube(
        [Y_AXIS.shaft_spacing - X_DRIVE.idler_x - X_DRIVE.motor_x, GT2.width, GT2.thickness]
    ).translate(
        [
            left_x + X_DRIVE.idler_x,
            gantry_y + X_BELT.y - GT2.width / 2,
            X_BELT.pulley_axis_z + PULLEY.pd / 2 - GT2.pitch_line_from_back,
        ]
    )


def _carriage_parts(ex: Exporter, gantry_y: float, carriage_x: float) -> None:
    """X carriage with wheels, fasteners and the pen holder."""
    items = _shift(carriage_assembly(), [carriage_x, gantry_y, 0])
    assert len(items) == 17
    ex.add("x_carriage", items[0], "carriage", GREEN)
    fasteners: list[Solid] = []
    for k, label in enumerate(("L", "R")):
        chunk = items[1 + 5 * k : 6 + 5 * k]
        ex.add(f"vwheel_{label}_top", chunk[0], "carriage", (40, 40, 40))
        ex.add(f"vwheel_{label}_bottom", chunk[2], "carriage", (40, 40, 40))
        fasteners += [chunk[1], chunk[3], chunk[4]]
    ex.add("carriage_fasteners", fasteners, "carriage", FASTENER)
    ex.add("x_belt_clamps", [items[11], items[13]], "carriage", GOLD)
    ex.add("x_belt_clamped", [items[12], items[14]], "carriage", DARK)
    ex.add("x_trigger", items[15:17], "carriage", FASTENER)

    head = pen_holder_items(pen_up=True)

    def place(solid: Solid) -> Solid:
        placed = solid.mirror([0, 1, 0]).translate([0, CARRIAGE.plate_front_y, 0])
        return translate(placed, [carriage_x, gantry_y, 0])

    ex.add("pen_body", place(head["body"]), "carriage", PRINTED_PEN)
    ex.add("pen_servo", place(head["servo"]), "carriage", MOTOR)
    ex.add(
        "pen_clamp_screws",
        [place(head["clamp_screw_0"]), place(head["clamp_screw_1"])],
        "carriage",
        FASTENER,
    )
    ex.add("pen_horn", [place(head["horn"]), place(head["pin"])], "carriage", SILVER)
    ex.add("pen_slide", place(head["slide"]), "slide", PRINTED)
    ex.add("pen_rod", place(head["rod"]), "slide", SILVER)
    ex.add("pen", place(head["pen"]), "slide", RED)
    ex.add(
        "pen_thumbscrew",
        [place(head["thumbscrew"]), place(head["thumbscrew_nut"])],
        "slide",
        FASTENER,
    )


def _axes(gantry_y: float, carriage_x: float) -> dict[str, Any]:
    """Joint frames: ``origin`` in the machine frame at the reference pose, ``dir`` the axis."""
    left_x, right_x = Y_AXIS.shaft_x
    d = Y_DRIVE
    belt_x = Y_AXIS.belt_x
    c = CARRIAGE
    p = PEN
    beam_z = BEAM.bottom_z + BEAM.height / 2
    horn_y = carriage_x, gantry_y + c.plate_front_y - p.horn_d[0]
    axes: dict[str, Any] = {
        "y_shaft_L": {"origin": [left_x, gantry_y, Y_AXIS.shaft_z], "dir": [0, 1, 0]},
        "y_shaft_R": {"origin": [right_x, gantry_y, Y_AXIS.shaft_z], "dir": [0, 1, 0]},
        "beam": {"origin": [carriage_x, gantry_y, beam_z], "dir": [1, 0, 0]},
        "y_idler_L": {
            "origin": [left_x + belt_x, d.idler_y, Y_AXIS.pulley_axis_z],
            "dir": [1, 0, 0],
        },
        "y_idler_R": {
            "origin": [right_x - belt_x, d.idler_y, Y_AXIS.pulley_axis_z],
            "dir": [1, 0, 0],
        },
        "y_pulley_L": {
            "origin": [left_x + belt_x, d.motor_y, Y_AXIS.pulley_axis_z],
            "dir": [1, 0, 0],
        },
        "y_pulley_R": {
            "origin": [right_x - belt_x, d.motor_y, Y_AXIS.pulley_axis_z],
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
        "pen_horn": {"origin": [carriage_x + p.servo_x, horn_y[1], p.shaft_z], "dir": [0, 1, 0]},
        "pen_slide": {
            "origin": [carriage_x + p.pen_x, gantry_y + c.plate_front_y, 0],
            "dir": [0, 0, 1],
        },
    }
    for k, label in enumerate("LR"):
        sx = -1 if k == 0 else 1
        for z, pos in zip(c.wheel_z, ("top", "bottom"), strict=True):
            axes[f"vwheel_{label}_{pos}"] = {
                "origin": [carriage_x + sx * WHEEL_X, gantry_y, z],
                "dir": [0, 1, 0],
            }
    return axes


def export_freecad(out_dir: Path = FREECAD_DIR) -> Path:
    """Write the component STLs and ``components.json``; returns the manifest path."""
    params.check_design()
    gantry_y = gantry_y_at(GANTRY_POS)
    carriage_x = carriage_x_at(CARRIAGE_POS)
    ex = Exporter()
    _fixed_parts(ex)
    _y_drive_parts(ex, gantry_y)
    _gantry_parts(ex, gantry_y)
    _carriage_parts(ex, gantry_y, carriage_x)
    ex.write(out_dir)
    manifest = {
        "reference_pose": {
            "gantry_y": gantry_y,
            "carriage_x": carriage_x,
            "pen": "up",
        },
        "travel": {
            "gantry_y": list(Y_AXIS.gantry_y_range),
            "carriage_x": list(CARRIAGE.center_x_range),
            "pen_lift": PEN.lift,
        },
        "axes": _axes(gantry_y, carriage_x),
        "components": ex.entries,
        "frame": {"board": list(FRAME.board_size), "bracket_len_y": BRACKET.len_y},
    }
    path = out_dir / "components.json"
    path.write_text(json.dumps(manifest, indent=1) + "\n")
    typer.echo(f"wrote {path}")
    return path
