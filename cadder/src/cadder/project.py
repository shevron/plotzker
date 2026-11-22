"""A cadder project: where its parts, assemblies, checks and files are.

A project module defines one :class:`Project` (``PROJECT``) and names it in its
``pyproject.toml``::

    [tool.cadder]
    project = "mypackage.project:PROJECT"

The registries are functions, so that listing commands and help don't build any geometry, and
so that subprocesses (renders, the design diff, FEM exports) can import the project by its
``spec`` alone.
"""

import importlib
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer

    from cadder.assembly import Assembly, AssemblyCheck
    from cadder.freecad.model import FreeCadAssembly
    from cadder.part import MaterialPart, Part


@dataclass(frozen=True, kw_only=True)
class Project:
    """Everything cadder's commands need to know about a project."""

    name: str
    #: ``"package.module:ATTRIBUTE"`` of this object, for subprocesses
    spec: str
    #: repository root: outputs and the files below are relative to it
    root: Path
    #: source folders that hold the project's packages (put on ``sys.path`` by subprocesses that
    #: build another revision), relative to ``root``
    source_dirs: tuple[str, ...] = ("src",)
    parts: Callable[[], Mapping[str, Part]]
    assemblies: Callable[[], Mapping[str, Assembly]] = dict
    assembly_checks: Callable[[], Mapping[str, AssemblyCheck]] = dict
    #: FreeCAD assemblies with rigid bodies and joints (the ``freecad`` command)
    freecad_assemblies: Callable[[], Mapping[str, FreeCadAssembly]] = dict
    #: design rules as ``(ok, message)`` pairs (``check`` and every export run them first)
    design_checks: Callable[[], Iterable[tuple[bool, str]]] | None = None
    #: key numbers printed by ``check``
    report: Callable[[], str] | None = None
    #: adds project-specific commands to the CLI
    commands: Callable[[typer.Typer], None] | None = None
    #: extra outputs written by ``all`` after the STLs (e.g. drawings); each returns its paths
    all_steps: tuple[Callable[[], object], ...] = ()
    #: the module whose diff the design diff shows next to changed parts, relative to ``root``
    params_file: str | None = None
    #: FEM verdicts file, relative to ``root``
    verdicts_file: str = "fem/verdicts.toml"
    #: ``("module:PARTS", "module:ASSEMBLIES")`` registries tried, in order, when the design
    #: diff builds a revision from before this project used cadder (dicts of build functions)
    legacy_specs: tuple[tuple[str, str], ...] = ()
    outputs: Mapping[str, str] = field(
        default_factory=lambda: {
            "stl": "stl",
            "renders": "renders",
            "fem": "fem/results",
            "freecad": "freecad",
            "build": "build",
        }
    )

    def path(self, output: str) -> Path:
        """Folder of an output kind: ``stl``, ``renders``, ``fem``, ``freecad`` or ``build``."""
        return self.root / self.outputs[output]

    @property
    def verdicts(self) -> Path:
        """The FEM verdicts file."""
        return self.root / self.verdicts_file

    def check_design(self) -> None:
        """Run the design rules; raise :class:`cadder.checks.DesignError` on a failure."""
        from cadder.checks import run_design_checks

        if self.design_checks is not None:
            run_design_checks(self.design_checks())

    def material_parts(self) -> dict[str, MaterialPart]:
        """The parts with a material (the ones an FEM check can run on)."""
        from cadder.part import MaterialPart

        return {n: p for n, p in self.parts().items() if isinstance(p, MaterialPart)}


def load_project(spec: str) -> Project:
    """The project object named by ``"package.module:ATTRIBUTE"``."""
    module_name, _, attribute = spec.partition(":")
    project = getattr(importlib.import_module(module_name), attribute or "PROJECT")
    if not isinstance(project, Project):
        raise TypeError(f"{spec} is not a cadder Project")
    return project


def find_spec(start: Path | None = None) -> str | None:
    """``[tool.cadder] project`` of the nearest ``pyproject.toml`` at or above ``start``."""
    folder = (start or Path.cwd()).resolve()
    for candidate in (folder, *folder.parents):
        pyproject = candidate / "pyproject.toml"
        if pyproject.is_file():
            with pyproject.open("rb") as f:
                spec = tomllib.load(f).get("tool", {}).get("cadder", {}).get("project")
            if spec:
                return str(spec)
    return None
