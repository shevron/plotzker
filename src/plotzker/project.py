"""The plotter as a cadder project; ``[tool.cadder] project`` in ``pyproject.toml`` names it.

The registries are imported on first use, so the CLI starts without building any geometry.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from cadder.project import Project

if TYPE_CHECKING:
    import typer
    from cadder.assembly import Assembly, AssemblyCheck
    from cadder.part import Part

ROOT = Path(__file__).resolve().parents[2]


def _parts() -> Mapping[str, Part]:
    from plotzker.parts import PARTS

    return PARTS


def _assemblies() -> Mapping[str, Assembly]:
    from plotzker.assemblies import ASSEMBLIES

    return ASSEMBLIES


def _assembly_checks() -> Mapping[str, AssemblyCheck]:
    from plotzker.assembly_checks import ASSEMBLY_CHECKS

    return ASSEMBLY_CHECKS


def _design_checks() -> Iterator[tuple[bool, str]]:
    from plotzker.params import design_checks

    return design_checks()


def _report() -> str:
    """Key numbers and the clearances of the moving parts."""
    from plotzker.assemblies.skeleton import clearance_report
    from plotzker.params import report

    return report() + "\n" + clearance_report()


def _commands(app: typer.Typer) -> None:
    from plotzker.cli import commands

    commands(app)


def _layout() -> object:
    from plotzker.cli import export_layout

    return export_layout()


PROJECT = Project(
    name="plotzker",
    spec="plotzker.project:PROJECT",
    root=ROOT,
    source_dirs=("src", "cadder/src"),
    parts=_parts,
    assemblies=_assemblies,
    assembly_checks=_assembly_checks,
    design_checks=_design_checks,
    report=_report,
    commands=_commands,
    all_steps=(_layout,),
    params_file="src/plotzker/params.py",
    # revisions before the cadder split (tag pre-cadder-split) and during it
    legacy_specs=(
        ("plotter_cad.parts:PRINTABLE_PARTS", "plotter_cad.assemblies:ASSEMBLIES"),
        ("plotzker.parts:PRINTABLE_PARTS", "plotzker.assemblies:ASSEMBLIES"),
    ),
)
