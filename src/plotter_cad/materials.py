"""Material data for the FEM checks, loaded from ``materials.toml``."""

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

MATERIALS_FILE = Path(__file__).with_name("materials.toml")


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


@cache
def _table() -> dict[str, dict[str, object]]:
    """The parsed ``materials.toml``."""
    with MATERIALS_FILE.open("rb") as f:
        return tomllib.load(f)


def material_names() -> list[str]:
    """Names of all known materials."""
    return list(_table())


def load_material(name: str) -> Material:
    """The material called ``name`` (a table in ``materials.toml``)."""
    table = _table()
    if name not in table:
        raise KeyError(f"Unknown material {name!r}. Available: {', '.join(table)}")
    try:
        return Material(name=name, **table[name])  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"materials.toml, [{name}]: {exc}") from exc
