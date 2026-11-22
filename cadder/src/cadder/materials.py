"""Materials and print profiles for the FEM checks, loaded from a project's TOML files.

A project keeps its data in two places: one TOML file of materials (a table per material) and a
folder of print profiles (``<name>.toml``, slicer settings plus the FEM knockdowns in a ``[fem]``
table). :class:`MaterialLibrary` reads them; cadder ships no data of its own.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Material:
    """A material, transversely isotropic about the build direction (MPa, g/cm³)."""

    name: str
    description: str
    density_g_cm3: float
    e_in_plane_mpa: float  #: Young's modulus within a layer
    e_build_mpa: float  #: Young's modulus across the layers
    nu_in_plane: float
    nu_build: float
    g_build_mpa: float  #: shear modulus in planes containing the build direction
    strength_in_plane_mpa: float
    strength_build_mpa: float  #: interlayer strength
    sustained_factor: float  #: share of the strength allowed for continuous loads
    assumed: bool
    source: str

    def __post_init__(self) -> None:
        """Reject values that cannot be a real material."""
        positive = (
            self.density_g_cm3,
            self.e_in_plane_mpa,
            self.e_build_mpa,
            self.g_build_mpa,
            self.strength_in_plane_mpa,
            self.strength_build_mpa,
        )
        if min(positive) <= 0:
            raise ValueError(f"material {self.name}: moduli, strengths and density must be > 0")
        if not (0 < self.nu_in_plane < 0.5 and 0 < self.nu_build < 0.5):
            raise ValueError(f"material {self.name}: Poisson ratios must be in (0, 0.5)")
        if not 0 < self.sustained_factor <= 1:
            raise ValueError(f"material {self.name}: sustained_factor must be in (0, 1]")


@dataclass(frozen=True)
class PrintProfile:
    """How a part is printed, and how a solid FEM model stands in for the real part."""

    name: str
    description: str
    material: str  #: name of a material in the same library
    nozzle_mm: float
    layer_height_mm: float
    perimeters: int
    infill_percent: float
    infill_pattern: str
    stiffness_factor: float  #: real part's stiffness relative to a solid print
    strength_factor: float  #: real part's strength relative to a solid print

    def __post_init__(self) -> None:
        """Reject values that cannot be a real print setup."""
        if min(self.nozzle_mm, self.layer_height_mm, self.perimeters) <= 0:
            raise ValueError(
                f"profile {self.name}: nozzle, layer height and perimeters must be > 0"
            )
        if not 0 <= self.infill_percent <= 100:
            raise ValueError(f"profile {self.name}: infill_percent must be in [0, 100]")
        if not (0 < self.stiffness_factor <= 1 and 0 < self.strength_factor <= 1):
            raise ValueError(f"profile {self.name}: FEM factors must be in (0, 1]")

    @property
    def wall_mm(self) -> float:
        """Thickness of the perimeter shell on each side."""
        return self.perimeters * self.nozzle_mm


@dataclass(frozen=True)
class MaterialLibrary:
    """A project's materials (``materials_file``) and print profiles (``profiles_dir``)."""

    materials_file: Path
    profiles_dir: Path
    default_profile: str = "default"
    _cache: dict[str, object] = field(default_factory=dict, compare=False, repr=False)

    def _materials(self) -> dict[str, dict[str, object]]:
        """The parsed materials file."""
        if "materials" not in self._cache:
            with self.materials_file.open("rb") as f:
                self._cache["materials"] = tomllib.load(f)
        return self._cache["materials"]  # type: ignore[return-value]

    def material_names(self) -> list[str]:
        """Names of all known materials."""
        return list(self._materials())

    def material(self, name: str) -> Material:
        """The material called ``name`` (a table in the materials file)."""
        table = self._materials()
        if name not in table:
            raise KeyError(f"Unknown material {name!r}. Available: {', '.join(table)}")
        try:
            return Material(name=name, **table[name])  # type: ignore[arg-type]
        except TypeError as exc:
            raise ValueError(f"{self.materials_file.name}, [{name}]: {exc}") from exc

    def profile_names(self) -> list[str]:
        """Names of all print profiles."""
        return sorted(p.stem for p in self.profiles_dir.glob("*.toml"))

    def profile(self, name: str | None = None) -> PrintProfile:
        """The print profile ``<profiles_dir>/<name>.toml`` (default: :attr:`default_profile`)."""
        name = name or self.default_profile
        key = f"profile:{name}"
        if key not in self._cache:
            self._cache[key] = self._load_profile(name)
        return self._cache[key]  # type: ignore[return-value]

    def _load_profile(self, name: str) -> PrintProfile:
        path = self.profiles_dir / f"{name}.toml"
        if not path.is_file():
            raise KeyError(
                f"Unknown print profile {name!r}. Available: {', '.join(self.profile_names())}"
            )
        with path.open("rb") as f:
            data = tomllib.load(f)
        fem = data.pop("fem", {})
        try:
            return PrintProfile(
                name=name,
                stiffness_factor=fem["stiffness_factor"],
                strength_factor=fem["strength_factor"],
                **data,
            )
        except (TypeError, KeyError) as exc:
            raise ValueError(
                f"{self.profiles_dir.name}/{name}.toml: missing or unexpected field {exc}"
            ) from exc
