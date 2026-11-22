"""The plotter's own commands, added to cadder's CLI (``python -m plotzker`` or ``cadder``).

    python -m plotzker layout     # baseboard drilling layout → docs/
    python -m plotzker freecad    # machine components for the FreeCAD assembly → freecad/

Every other command (check, stl, render, part, fem, fem-status, diff, all) is cadder's.
"""

from pathlib import Path
from typing import Annotated

import typer
from cadder.cli import reports_errors, run
from cadder.render import shown

from plotzker.project import PROJECT

DOCS_DIR = PROJECT.root / "docs"


def export_layout(out_dir: Path = DOCS_DIR) -> list[Path]:
    """Write the 1:1 baseboard drilling layout (SVG + hole table); returns the paths."""
    from plotzker.layout import write_layout

    PROJECT.check_design()
    written = write_layout(out_dir)
    for path in written:
        typer.echo(f"wrote {shown(PROJECT, path)}")
    return written


def commands(app: typer.Typer) -> None:
    """Add the plotter's commands to the app."""

    @app.command("layout")
    @reports_errors
    def layout_command(
        out: Annotated[Path, typer.Option(help="Output folder.")] = DOCS_DIR,
    ) -> None:
        """Write the baseboard drilling layout (SVG + table)."""
        export_layout(out)

    @app.command("freecad")
    @reports_errors
    def freecad_command() -> None:
        """Export the machine components for the FreeCAD assembly."""
        from plotzker.freecad_export import export_freecad

        export_freecad()


def main() -> None:
    """Entry point of ``plotzker`` and ``python -m plotzker``."""
    run(PROJECT, prog_name="python -m plotzker")
