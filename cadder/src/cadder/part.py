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

    def describe(self) -> list[str]:
        """Its lines in a part's summary."""
        lines = [f"  safety factor {self.safety_factor:g}"]
        for case in self.load_cases:
            kind = "sustained" if case.sustained else "peak"
            lines.append(f"  load case {case.name} ({kind}): {case.description}")
        lines += [f"  support {s.name}: {s.description}" for s in self.supports]
        for limit in self.displacement_limits:
            along = f"along {limit.direction}" if limit.direction else "magnitude"
            lines.append(f"  limit {limit.name}: {limit.limit_mm:g} mm {along}")
        return lines

    def to_dict(self) -> dict[str, object]:
        """The specification as JSON-ready data."""
        limits = self.displacement_limits
        return {
            "safety_factor": self.safety_factor,
            "load_cases": plain(self.load_cases),
            "supports": plain(self.supports),
            "displacement_limits": plain(limits),
            "default_displacement_limit_mm": None if limits else self.default_displacement_limit_mm,
        }


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

    def unchecked_state(self) -> str | None:
        """Why no FEM verdict applies to this part, or ``None`` if one should."""
        return self.fem_status

    def analysis_geometry(self) -> Solid:
        """The part in its analysis frame."""
        return self.build()

    def listing(self) -> str:
        """Its line in the list of parts."""
        return f"{self.name:<28} ({self.fem_status})"

    def describe(self) -> list[str]:
        """A readable summary, line by line."""
        return [f"{self.name}: {self.description}", f"  {self.fem_status}"]

    def to_dict(self) -> dict[str, object]:
        """Everything an FEM check (or its reviewer) needs about the part, as JSON-ready data.

        Hashed for the FEM verdicts: keep the keys and their order stable.
        """
        return {**self._header(), "fem_status": self.fem_status}

    def _header(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "units": "mm, N, MPa, degrees, mm/s²; displacement and loads in the analysis frame",
        }


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
        """Material values of the real part: the solid values, scaled by its knockdowns."""
        stiffness, strength = self._knockdowns()
        material = self.material
        return {
            "e_in_plane_mpa": material.e_in_plane_mpa * stiffness,
            "e_build_mpa": material.e_build_mpa * stiffness,
            "g_build_mpa": material.g_build_mpa * stiffness,
            "strength_in_plane_mpa": material.strength_in_plane_mpa * strength,
            "strength_build_mpa": material.strength_build_mpa * strength,
            "sustained_strength_in_plane_mpa": material.strength_in_plane_mpa * strength * material.sustained_factor,
            "sustained_strength_build_mpa": material.strength_build_mpa * strength * material.sustained_factor,
        }

    def _knockdowns(self) -> tuple[float, float]:
        """Stiffness and strength factors on the solid material values: none for a solid part."""
        return 1.0, 1.0

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

    def unchecked_state(self) -> str | None:
        """Why no FEM verdict applies to this part, or ``None`` if one should."""
        if not self.structural:
            return "not structural"
        if self.mirror_of:
            return f"covered by {self.mirror_of}"
        return None if self.fem else "NEEDS A SPEC"

    @property
    def frame_name(self) -> str:
        """The analysis frame as reports and the serialized form call it."""
        return self.frame

    def listing(self) -> str:
        return f"{self.name:<28} {self._setup_label()} FEM: {self.fem_status}"

    def describe(self) -> list[str]:
        assumed = " (assumed values)" if self.material.assumed else ""
        lines = [
            f"{self.name}: {self.description}",
            *self._setup_lines(),
            f"  material {self.material.name}: {self.material.description}{assumed}",
            f"  FEM: {self.fem_status}",
        ]
        if self.fem:
            lines += self.fem.describe()
        return lines

    def _setup_label(self) -> str:
        return f"{self.material.name:<14}"

    def _setup_lines(self) -> list[str]:
        return [f"  analysis frame: {self.frame}; material axis {self.material_axis}"]

    def to_dict(self) -> dict[str, object]:
        data = {
            **self._header(),
            "frame": self.frame_name,
            **self._axis_entry(),
            "structural": self.structural,
            "fem_status": self.fem_status,
            "mirror_of": self.mirror_of,
            **self._profile_entry(),
            "material": plain(self.material),
            "effective_properties": self.effective_properties(),
        }
        if self.fem is not None:
            data["fem"] = self.fem.to_dict()
        return data

    def _axis_entry(self) -> dict[str, object]:
        return {"material_axis": None if self.material_axis is None else list(self.material_axis)}

    def _profile_entry(self) -> dict[str, object]:
        return {}


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

    @property
    def frame_name(self) -> str:
        return self.OUTPUT_FRAME if self.frame == "output" else self.frame

    def _knockdowns(self) -> tuple[float, float]:
        return self.profile.stiffness_factor, self.profile.strength_factor

    def _setup_label(self) -> str:
        return f"{self.profile.name}/{self.material.name:<6}"

    def _setup_lines(self) -> list[str]:
        return [
            f"  analysis frame: {self.frame_name}; build direction {self.build_direction}",
            f"  print profile '{self.profile.name}': {self.profile.description}",
        ]

    def _axis_entry(self) -> dict[str, object]:
        return {"build_direction": list(self.build_direction)}

    def _profile_entry(self) -> dict[str, object]:
        return {"profile": plain(self.profile)}

    def assumed_inputs(self) -> list[str]:
        """The material's assumptions and the profile's knockdown factors."""
        return [
            *super().assumed_inputs(),
            f"print profile {self.profile.name}: infill knockdown factors",
        ]


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
