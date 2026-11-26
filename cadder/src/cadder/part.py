"""Parts: what a project makes or buys, with everything the checks need to know about it.

* :class:`Part`: a name, a description and the geometry in its output orientation (the STL).
* :class:`MaterialPart`: a concrete part of a known material (a plywood or metal plate, a
  purchased part, a print), with an optional :class:`FemSpec`: load cases, supports and allowed
  deflections.
* :class:`PrintedPart`: an FDM print, adding the print profile and the build direction (layer
  normal), which is also the axis of the material's layered properties.

Units: mm, N, MPa, degrees, mm/s². Loads, supports and limits are given in the part's analysis
frame (:attr:`MaterialPart.frame`): its output frame (the STL) or the installed frame (the
part's assembly frame, where loads are easiest to state).
"""

import dataclasses
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from cadder.materials import Material, PrintProfile
from cadder.regions import Region
from cadder.types import Frame, Vec3

if TYPE_CHECKING:
    from pythonscad import Solid

#: Safety factor on strength when a part doesn't state one: deliberately large while the
#: material values are assumed.
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


@dataclass(frozen=True, kw_only=True)
class Part:
    """A part of the project: a name, a description and its geometry."""

    name: str  #: registry key and STL file name
    description: str
    build: Callable[[], Solid]  #: in its output orientation (print bed, cutting sheet...)
    stl: bool = True  #: exported by the ``stl`` command (False: e.g. a purchased part)

    @property
    def fem_status(self) -> str:
        """FEM state for listings: a part without a material has no data for a check."""
        return "no material or FEM data yet"


@dataclass(frozen=True, kw_only=True)
class MaterialPart(Part):
    """A concrete part of a known material, with an optional FEM specification."""

    material: Material
    #: the material's distinct axis (panel normal of plywood, layer normal of a print) in
    #: ``frame``; ``None`` for an isotropic material
    material_axis: Vec3 | None = None
    frame: Frame = "output"
    #: the geometry in ``frame`` when that is not the output frame (``None``: :attr:`build`)
    analysis: Callable[[], Solid] | None = None
    structural: bool = True  #: carries load, so it needs an FEM check
    fem: FemSpec | None = None
    mirror_of: str | None = None  #: exact mirror image of this part: its check applies

    def __post_init__(self) -> None:
        """Check the axis, the analysis geometry and the FEM state."""
        if self.material_axis is not None and math.isclose(math.hypot(*self.material_axis), 0):
            raise ValueError(f"part {self.name}: zero material axis")
        if self.frame == "installed" and self.analysis is None:
            raise ValueError(f"part {self.name}: an installed analysis frame needs `analysis`")
        if self.fem is not None and not self.structural:
            raise ValueError(f"part {self.name}: a non-structural part has no FEM spec")

    def analysis_geometry(self) -> Solid:
        """The part in its analysis frame."""
        return (self.analysis or self.build)()

    @property
    def axis(self) -> Vec3:
        """The material axis, or z for an isotropic material (any axis will do)."""
        return self.material_axis or (0.0, 0.0, 1.0)

    def effective_properties(self) -> dict[str, float]:
        """Material values of the real part (the solid values, no knockdowns)."""
        return effective_properties(self.material)

    def assumed_inputs(self) -> list[str]:
        """Inputs of the check that are assumptions, for its report."""
        if self.material.assumed:
            return [f"material {self.material.name}: {self.material.source}"]
        return []

    @property
    def fem_status(self) -> str:
        """``specified``, ``missing`` (structural, no spec yet) or ``not structural``."""
        if not self.structural:
            return "not structural"
        if self.mirror_of:
            return f"mirror of {self.mirror_of}"
        return "specified" if self.fem else "missing"


@dataclass(frozen=True, kw_only=True)
class PrintedPart(MaterialPart):
    """An FDM-printed part: print profile and build direction (layer normal)."""

    #: name of the output frame in reports and the serialized form (the print bed)
    OUTPUT_FRAME: ClassVar[str] = "print"

    profile: PrintProfile
    build_direction: Vec3  #: layer normal, pointing up from the bed, in ``frame``

    def __post_init__(self) -> None:
        """The build direction is the material axis."""
        if math.isclose(math.hypot(*self.build_direction), 0):
            raise ValueError(f"part {self.name}: zero build direction")
        object.__setattr__(self, "material_axis", self.build_direction)
        super().__post_init__()

    def effective_properties(self) -> dict[str, float]:
        """Material values of the real part: scaled by the profile's knockdowns."""
        return effective_properties(self.material, self.profile)

    def assumed_inputs(self) -> list[str]:
        """The material's assumptions and the profile's knockdown factors."""
        return [
            *super().assumed_inputs(),
            f"print profile {self.profile.name}: infill knockdown factors",
        ]


def effective_properties(material: Material, profile: PrintProfile | None = None) -> dict[str, float]:
    """Material values of a real part: the solid values, scaled by a print profile's knockdowns
    when there is one."""
    k_e, k_s = (profile.stiffness_factor, profile.strength_factor) if profile else (1.0, 1.0)
    return {
        "e_in_plane_mpa": material.e_in_plane_mpa * k_e,
        "e_build_mpa": material.e_build_mpa * k_e,
        "g_build_mpa": material.g_build_mpa * k_e,
        "strength_in_plane_mpa": material.strength_in_plane_mpa * k_s,
        "strength_build_mpa": material.strength_build_mpa * k_s,
        "sustained_strength_in_plane_mpa": material.strength_in_plane_mpa * k_s * material.sustained_factor,
        "sustained_strength_build_mpa": material.strength_build_mpa * k_s * material.sustained_factor,
    }


def plain(obj: object) -> object:
    """Dataclasses, tuples and dicts as JSON-ready dicts and lists. A dataclass gets a ``type``:
    its class's ``SERIAL_NAME``, or the lower-case class name."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        data = {f.name: plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        kind = getattr(type(obj), "SERIAL_NAME", type(obj).__name__.lower())
        return {"type": kind, **data}
    if isinstance(obj, tuple | list):
        return [plain(v) for v in obj]
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items()}
    return obj


def part_to_dict(part: Part) -> dict[str, object]:
    """Everything an FEM check (or its reviewer) needs about ``part``, as JSON-ready data.

    Hashed for the FEM verdicts: keep the keys and their order stable.
    """
    data: dict[str, object] = {
        "name": part.name,
        "description": part.description,
        "units": "mm, N, MPa, degrees, mm/s²; displacement and loads in the analysis frame",
    }
    if not isinstance(part, MaterialPart):
        data["fem_status"] = part.fem_status
        return data
    printed = isinstance(part, PrintedPart)
    data["frame"] = PrintedPart.OUTPUT_FRAME if printed and part.frame == "output" else part.frame
    if isinstance(part, PrintedPart):
        data["build_direction"] = list(part.build_direction)
    else:
        data["material_axis"] = None if part.material_axis is None else list(part.material_axis)
    data["structural"] = part.structural
    data["fem_status"] = part.fem_status
    data["mirror_of"] = part.mirror_of
    if isinstance(part, PrintedPart):
        data["profile"] = plain(part.profile)
    data["material"] = plain(part.material)
    data["effective_properties"] = part.effective_properties()
    if part.fem is not None:
        spec = part.fem
        limits = spec.displacement_limits
        data["fem"] = {
            "safety_factor": spec.safety_factor,
            "load_cases": plain(spec.load_cases),
            "supports": plain(spec.supports),
            "displacement_limits": plain(limits),
            "default_displacement_limit_mm": None if limits else spec.default_displacement_limit_mm,
        }
    return data
