"""A printable part with everything the checks need to know about it, in one place.

A :class:`Part` bundles the geometry function, the print profile and material, the build
direction (layer normal) and, for structural parts, a :class:`FemSpec`: load cases, supports and
the allowed deflections. ``python -m plotzker part <name> --json`` prints it for the FEM
sub-agent (``docs/fem-subagent-plan.md``).

Units: mm, N, MPa, degrees, mm/s². Loads, supports and limits are given in the part's analysis
frame (:attr:`Part.frame`): the print frame (the STL) or the installed frame (the part's
assembly frame, where loads are easiest to state).
"""

import dataclasses
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from plotzker.materials import Material, load_material
from plotzker.print_profile import DEFAULT_PROFILE, PrintProfile, load_profile
from plotzker.regions import Region
from plotzker.types import Frame, Vec3

if TYPE_CHECKING:
    from pythonscad import Solid

#: Safety factor on strength when a part doesn't state one. DESIGN: deliberately large until
#: the material values are measured (docs/fem-subagent-plan.md).
DEFAULT_SAFETY_FACTOR = 3.0
#: Allowed displacement when a part states no limits (mm).
DEFAULT_DISPLACEMENT_LIMIT_MM = 0.1


@dataclass(frozen=True)
class Force:
    """A force spread over the faces of a region (total vector, N)."""

    region: Region
    vector: Vec3
    #: Bearing load (an axle in a bore): the share of each face falls off with the cosine of the
    #: angle between its normal and the force, so it is zero at the edges of the contact.
    bearing: bool = False


@dataclass(frozen=True)
class Moment:
    """A pure couple applied to the faces of a region as linearly varying forces (N·mm)."""

    region: Region
    vector: Vec3


@dataclass(frozen=True)
class Acceleration:
    """Inertial load of the whole part from an acceleration (mm/s²)."""

    vector: Vec3


Load = Force | Moment | Acceleration


@dataclass(frozen=True)
class LoadCase:
    """Loads that act together, with where the numbers come from."""

    name: str
    description: str
    loads: tuple[Load, ...]
    source: str
    assumed: bool = True  #: the magnitudes are assumptions, not measurements
    sustained: bool = False  #: acts continuously (creep applies), vs. a short peak
    safety_factor: float | None = None  #: overrides the part's


@dataclass(frozen=True)
class Support:
    """Faces of a region held fixed in the directions marked in ``constrain`` (x, y, z)."""

    name: str
    region: Region
    description: str
    constrain: tuple[bool, bool, bool] = (True, True, True)


@dataclass(frozen=True)
class DisplacementLimit:
    """Allowed displacement of the mesh nodes in a region.

    With a ``direction`` the check is on the displacement component along it (absolute value),
    otherwise on the magnitude. Several limits on one region give directional budgets.
    """

    name: str
    region: Region
    limit_mm: float
    direction: Vec3 | None = None
    load_cases: tuple[str, ...] = ()  #: empty: all load cases
    assumed: bool = True


@dataclass(frozen=True)
class FemSpec:
    """What the FEM check needs besides geometry and material."""

    load_cases: tuple[LoadCase, ...]
    supports: tuple[Support, ...]
    displacement_limits: tuple[DisplacementLimit, ...] = ()
    safety_factor: float = DEFAULT_SAFETY_FACTOR
    #: Allowed displacement (mm) of the whole part when no limits are given; ``None``: strength
    #: only (parts that carry only abuse loads, where deflection doesn't matter)
    default_displacement_limit_mm: float | None = DEFAULT_DISPLACEMENT_LIMIT_MM

    def __post_init__(self) -> None:
        """Check names, supports and references between the pieces."""
        names = [c.name for c in self.load_cases]
        if not names or len(set(names)) != len(names):
            raise ValueError("load case names must be unique and there must be at least one")
        if not self.supports:
            raise ValueError("a part needs at least one support")
        known = set(names)
        for limit in self.displacement_limits:
            if limit.limit_mm <= 0 or not set(limit.load_cases) <= known:
                raise ValueError(f"displacement limit {limit.name}: bad limit or load case name")


@dataclass(frozen=True)
class Part:
    """A printable part: geometry, print setup, build direction and FEM specification."""

    name: str  #: STL name, as in ``PRINTABLE_PARTS``
    description: str
    build: Callable[[], Solid]  #: the part in its analysis frame
    frame: Frame
    build_direction: Vec3  #: layer normal, pointing up from the bed, in ``frame``
    profile: str = DEFAULT_PROFILE
    material: str | None = None  #: overrides the profile's
    structural: bool = True  #: carries load, so it needs an FEM check
    fem: FemSpec | None = None
    mirror_of: str | None = None  #: exact mirror image of this part: its check applies

    def __post_init__(self) -> None:
        """Check the build direction and the FEM state."""
        if math.isclose(math.hypot(*self.build_direction), 0):
            raise ValueError(f"part {self.name}: zero build direction")
        if self.fem is not None and not self.structural:
            raise ValueError(f"part {self.name}: a non-structural part has no FEM spec")

    @property
    def print_profile(self) -> PrintProfile:
        """The part's print profile."""
        return load_profile(self.profile)

    @property
    def material_data(self) -> Material:
        """The part's material."""
        return load_material(self.material or self.print_profile.material)

    @property
    def fem_status(self) -> str:
        """``specified``, ``missing`` (structural, no spec yet) or ``not structural``."""
        if not self.structural:
            return "not structural"
        if self.mirror_of:
            return f"mirror of {self.mirror_of}"
        return "specified" if self.fem else "missing"


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
class Assembly:
    """Parts that work together, checked on the sum of their deflections and play.

    Each part is checked on its own with the others held rigid (``Part.fem``); the sum is what
    the machine sees, so it is judged here from the members' recorded results
    (``python -m plotzker fem-assembly``). Play between the parts (clearances) has no
    stiffness for the FEM to find, so it enters as rigid terms computed from the geometry.
    """

    name: str
    description: str
    members: tuple[str, ...]  #: part names (a mirror image's check is its base part's)
    limits: tuple[AssemblyLimit, ...]
    source: str = ""  #: where the limits and the play model come from


def assembly_to_dict(assembly: Assembly) -> dict[str, object]:
    """The assembly as plain JSON-ready data."""
    return _plain(assembly)  # type: ignore[return-value]


def effective_properties(material: Material, profile: PrintProfile) -> dict[str, float]:
    """Material values of a real part: the solid values scaled by the profile's knockdowns."""
    k_e, k_s = profile.stiffness_factor, profile.strength_factor
    return {
        "e_in_plane_mpa": material.e_in_plane_mpa * k_e,
        "e_build_mpa": material.e_build_mpa * k_e,
        "g_build_mpa": material.g_build_mpa * k_e,
        "strength_in_plane_mpa": material.strength_in_plane_mpa * k_s,
        "strength_build_mpa": material.strength_build_mpa * k_s,
        "sustained_strength_in_plane_mpa": material.strength_in_plane_mpa
        * k_s
        * material.sustained_factor,
        "sustained_strength_build_mpa": material.strength_build_mpa
        * k_s
        * material.sustained_factor,
    }


def _plain(obj: object) -> object:
    """Dataclasses, tuples and dicts as JSON-ready dicts and lists (dataclasses get a ``type``)."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        data = {f.name: _plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        return {"type": type(obj).__name__.lower(), **data}
    if isinstance(obj, tuple | list):
        return [_plain(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    return obj


def part_to_dict(part: Part) -> dict[str, object]:
    """Everything the FEM sub-agent needs about ``part``, as plain JSON-ready data."""
    profile, material = part.print_profile, part.material_data
    data: dict[str, object] = {
        "name": part.name,
        "description": part.description,
        "units": "mm, N, MPa, degrees, mm/s²; displacement and loads in the analysis frame",
        "frame": part.frame,
        "build_direction": list(part.build_direction),
        "structural": part.structural,
        "fem_status": part.fem_status,
        "mirror_of": part.mirror_of,
        "profile": _plain(profile),
        "material": _plain(material),
        "effective_properties": effective_properties(material, profile),
    }
    if part.fem is not None:
        spec = part.fem
        limits = spec.displacement_limits
        data["fem"] = {
            "safety_factor": spec.safety_factor,
            "load_cases": _plain(spec.load_cases),
            "supports": _plain(spec.supports),
            "displacement_limits": _plain(limits),
            "default_displacement_limit_mm": None if limits else spec.default_displacement_limit_mm,
        }
    return data
