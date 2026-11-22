"""The demo project: a block printed on a plate, an assembly and a FreeCAD assembly."""

from collections.abc import Iterator
from pathlib import Path

from pythonscad import cube

from cadder.assembly import Assembly
from cadder.freecad import Body, Component, FreeCadAssembly, Joint
from cadder.materials import MaterialLibrary
from cadder.part import FemSpec, Force, LoadCase, MaterialPart, Part, PrintedPart, Support
from cadder.project import Project
from cadder.regions import Box

HERE = Path(__file__).parent
LIBRARY = MaterialLibrary(HERE / "materials.toml", HERE / "profiles")
PROFILE = LIBRARY.profile()

#: The block: 20 × 10 × 10, fixed at x = 0, pushed down at x = 20
BLOCK = PrintedPart(
    name="block",
    description="A printed block, loaded as a cantilever",
    build=lambda: cube([20, 10, 10]),
    build_direction=(0, 0, 1),
    profile=PROFILE,
    material=LIBRARY.material(PROFILE.material),
    fem=FemSpec(
        load_cases=(
            LoadCase(
                "push",
                "pushed down at the free end",
                (Force(Box((19.5, -1, -1), (20.5, 11, 11), facing=(1, 0, 0)), (0, 0, -10)),),
                "test",
            ),
        ),
        supports=(Support("wall", Box((-0.5, -1, -1), (0.5, 11, 11), facing=(-1, 0, 0)), ""),),
    ),
)
#: A steel plate the block sits on (not exported: bought cut to size)
PLATE = MaterialPart(
    name="plate",
    description="A steel plate",
    build=lambda: cube([40, 20, 2]),
    material=LIBRARY.material("steel"),
    structural=False,
    stl=False,
)
#: A part with no material yet
TAG = Part(name="tag", description="A printed tag", build=lambda: cube([5, 5, 1]))

PARTS: dict[str, Part] = {p.name: p for p in (BLOCK, PLATE, TAG)}

ASSEMBLIES = {
    "stack": Assembly(
        name="stack",
        description="The block on the plate",
        build=lambda: [PLATE.build(), BLOCK.build().translate([10, 5, 2])],
    )
}


def _components() -> list[Component]:
    return [
        Component("plate", PLATE.build(), "base", (200, 200, 200)),
        Component("block_0", BLOCK.build().translate([0, 5, 2]), "slider", (255, 140, 0)),
        Component("block_1", BLOCK.build().translate([20, 5, 2]), "slider", (255, 140, 0)),
    ]


def _joints() -> list[Joint]:
    return [Joint("Slider", "plate", "block_0", (10, 10, 2), (1, 0, 0), "Block slides", (-5, 5))]


SLIDE = FreeCadAssembly(
    name="Slide",
    label="Demo slide",
    description="Two blocks sliding on the plate",
    components=_components,
    bodies=(Body("base", "plate", grounded=True), Body("slider", "block_0")),
    joints=_joints,
)


def _checks() -> Iterator[tuple[bool, str]]:
    yield PLATE.build is not None, "the plate exists"
    yield BLOCK.fem is not None, "the block has an FEM spec"


PROJECT = Project(
    name="demo",
    spec="demo.project:PROJECT",
    root=HERE.parents[1],
    parts=lambda: PARTS,
    assemblies=lambda: ASSEMBLIES,
    freecad_assemblies=lambda: {SLIDE.name: SLIDE},
    design_checks=_checks,
    report=lambda: "block: 20 × 10 × 10",
)
