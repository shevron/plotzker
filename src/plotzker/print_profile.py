"""Print profiles (slicer settings and their FEM knockdowns), loaded from ``profiles/*.toml``."""

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROFILE_DIR = Path(__file__).with_name("profiles")
DEFAULT_PROFILE = "default"


@dataclass(frozen=True)
class PrintProfile:
    """How a part is printed, and how a solid FEM model stands in for the real part."""

    name: str
    description: str
    material: str  #: name in ``materials.toml``
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


def profile_names() -> list[str]:
    """Names of all print profiles."""
    return sorted(p.stem for p in PROFILE_DIR.glob("*.toml"))


@cache
def load_profile(name: str = DEFAULT_PROFILE) -> PrintProfile:
    """The print profile ``profiles/<name>.toml``."""
    path = PROFILE_DIR / f"{name}.toml"
    if not path.is_file():
        raise KeyError(f"Unknown print profile {name!r}. Available: {', '.join(profile_names())}")
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
        raise ValueError(f"profiles/{name}.toml: missing or unexpected field {exc}") from exc
