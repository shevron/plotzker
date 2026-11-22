"""Assemblies: parts placed or checked together.

* :class:`Assembly`: parts and hardware placed for a fit check, a render and the design diff.
* :class:`AssemblyCheck`: parts checked together on the sum of their FEM deflections and the
  play between them (each part's own check holds its neighbours rigid).

FreeCAD assemblies with rigid bodies and joints are :mod:`cadder.freecad`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from cadder.part import plain

if TYPE_CHECKING:
    from pythonscad import Solid


@dataclass(frozen=True, kw_only=True)
class Assembly:
    """Parts and hardware models placed together; ``build`` returns colored solids."""

    name: str  #: registry key and render name
    description: str
    build: Callable[[], list[Solid]]


@dataclass(frozen=True)
class AssemblyTerm:
    """One contribution to an assembly's budget: a member part's FEM displacement (the named
    displacement limit of its check) or a rigid offset that the FEM cannot see (clearance)."""

    description: str
    part: str | None = None  #: member part whose check supplies the value
    criterion: str | None = None  #: its displacement limit's name
    rigid_mm: float = 0.0  #: a fixed offset, from geometry


@dataclass(frozen=True)
class AssemblyLimit:
    """Allowed total displacement along one direction: the sum of the terms (worst case: the
    parts' deflections and the play add up)."""

    name: str
    limit_mm: float
    terms: tuple[AssemblyTerm, ...]


@dataclass(frozen=True)
class AssemblyCheck:
    """Parts that work together, checked on the sum of their deflections and play.

    Each part is checked on its own with the others held rigid (``MaterialPart.fem``); the sum is
    what the machine sees, so it is judged here from the members' recorded results (the ``fem``
    command). Play between the parts (clearances) has no
    stiffness for the FEM to find, so it enters as rigid terms computed from the geometry.
    """

    #: ``type`` in the serialized form (the class's earlier name: keeps the verdict hashes)
    SERIAL_NAME: ClassVar[str] = "assembly"

    name: str
    description: str
    members: tuple[str, ...]  #: part names (a mirror image's check is its base part's)
    limits: tuple[AssemblyLimit, ...]
    source: str = ""  #: where the limits and the play model come from


def assembly_to_dict(assembly: AssemblyCheck) -> dict[str, object]:
    """The assembly check as plain JSON-ready data."""
    return plain(assembly)  # type: ignore[return-value]
