"""The plotter's materials (``materials.toml``) and print profiles (``profiles/*.toml``)."""

from pathlib import Path

from cadder.materials import Material, MaterialLibrary, PrintProfile

HERE = Path(__file__).parent
LIBRARY = MaterialLibrary(HERE / "materials.toml", HERE / "profiles")
DEFAULT_PROFILE = LIBRARY.default_profile


def load_material(name: str) -> Material:
    """The material called ``name`` (a table in ``materials.toml``)."""
    return LIBRARY.material(name)


def load_profile(name: str = DEFAULT_PROFILE) -> PrintProfile:
    """The print profile ``profiles/<name>.toml``."""
    return LIBRARY.profile(name)


def material_names() -> list[str]:
    """Names of all known materials."""
    return LIBRARY.material_names()


def profile_names() -> list[str]:
    """Names of all print profiles."""
    return LIBRARY.profile_names()
