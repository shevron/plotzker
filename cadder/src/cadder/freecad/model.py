"""The definition of a FreeCAD assembly: components, rigid bodies and joints.

A project builds these in plain Python (no FreeCAD needed); :mod:`cadder.freecad.export`
writes them out and :mod:`cadder.freecad.build` turns them into a FreeCAD 1.x Assembly.

Inside each rigid body every component is held to the body's root by a Fixed joint, which the
builder adds itself. The explicit :class:`Joint`\\ s give the assembly its motion: between
bodies (a slider that carries one body on another) or inside a body (a wheel that turns on its
axle); a component that is the second end (``b``) of a joint inside its own body is not fixed.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from cadder.types import Vec3

if TYPE_CHECKING:
    from pythonscad import Solid

RGB = tuple[int, int, int]

#: FreeCAD Assembly joint types cadder writes
JointKind = Literal["Fixed", "Revolute", "Cylindrical", "Slider", "Ball"]


@dataclass(frozen=True)
class Component:
    """One object of the assembly: a part, a purchased part, or a group of fasteners."""

    name: str
    solid: Solid | Sequence[Solid]  #: a list (e.g. the screws of one joint) is united
    body: str  #: the rigid body it moves with
    color: RGB
    #: name of the shared mesh when other components are the same shape (default: the first
    #: one's name without a side / position / number suffix)
    shape: str | None = None
    transparency: int = 0  #: percent


@dataclass(frozen=True)
class Body:
    """A rigid body: components fixed to ``root``; one body is grounded."""

    name: str
    root: str
    grounded: bool = False


@dataclass(frozen=True)
class Joint:
    """A joint between components ``a`` and ``b`` (``b`` is the one that moves on ``a``).

    The joint frame is at ``origin`` with its z axis along ``direction`` (the slide or rotation
    axis), in the assembly frame. ``limits`` (Slider: mm; Revolute: degrees) are relative to the
    modeled position.
    """

    kind: JointKind
    a: str
    b: str
    origin: Vec3
    direction: Vec3
    label: str
    limits: tuple[float, float] | None = None


@dataclass(frozen=True)
class FreeCadAssembly:
    """A FreeCAD assembly to build: ``<name>.FCStd``."""

    name: str  #: file and document name
    label: str  #: shown in FreeCAD's tree
    description: str
    components: Callable[[], Sequence[Component]]
    bodies: Sequence[Body]
    joints: Callable[[], Sequence[Joint]]
    #: stored in the manifest only (reference pose, travel...)
    metadata: Callable[[], Mapping[str, object]] = field(default=dict)

    def check(self, components: Sequence[Component], joints: Sequence[Joint]) -> None:
        """Raise ``ValueError`` if names, bodies or joint ends don't match up."""
        names = [c.name for c in components]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.name}: component names must be unique")
        known_bodies = {b.name for b in self.bodies}
        if sum(b.grounded for b in self.bodies) != 1:
            raise ValueError(f"{self.name}: exactly one body must be grounded")
        for c in components:
            if c.body not in known_bodies:
                raise ValueError(f"{self.name}: component {c.name} in unknown body {c.body}")
        for b in self.bodies:
            if b.root not in names:
                raise ValueError(f"{self.name}: body {b.name} has unknown root {b.root}")
        for j in joints:
            if j.a not in names or j.b not in names:
                raise ValueError(f"{self.name}: joint {j.label!r} names an unknown component")


class Components(list[Component]):
    """A list of components with a shorthand to add one."""

    def add(
        self,
        name: str,
        solid: Solid | Sequence[Solid],
        body: str,
        color: RGB,
        shape: str | None = None,
        transparency: int = 0,
    ) -> None:
        """Append a component."""
        self.append(Component(name, solid, body, color, shape, transparency))
