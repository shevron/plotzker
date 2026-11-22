"""Build outputs: design checks, STL export and PNG renders.

Usage (from the repository root, with the package installed or ``src`` on the path)::

    python -m plotzker check            # design checks + key numbers
    python -m plotzker stl              # all printable parts → stl/
    python -m plotzker stl x_carriage   # one part
    python -m plotzker render           # parts + assemblies → renders/*.png
    python -m plotzker render --inspect # all views → renders/inspect/<name>_<view>.png
    python -m plotzker part --list      # parts with profile, material and FEM state
    python -m plotzker part NAME [--json]  # a part's print/FEM properties (--json: sub-agent)
    python -m plotzker fem-status       # FEM state of every part, stale verdicts flagged
    python -m plotzker fem NAME...      # FEM check of parts → fem/results/, fem/verdicts.toml
    python -m plotzker diff [A [B]]     # parts changed between git revisions
    python -m plotzker layout           # baseboard drilling layout → docs/
    python -m plotzker freecad          # machine components for the FreeCAD assembly → freecad/
    python -m plotzker all              # check, stl, render, layout

The CLI is a Typer app (the project standard for command-line tools).

STL export uses the ``pythonscad`` Python module. PNG rendering needs the PythonSCAD
application (``pythonscad`` on the PATH, or ``--pythonscad PATH`` / ``$PYTHONSCAD``):
the pip module has no image export.
"""

import functools
import os
import shutil
import subprocess
import tempfile
import textwrap
from collections.abc import Callable, Collection, Iterable
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from plotzker import params

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = Path(__file__).resolve().parents[1]
STL_DIR = REPO_ROOT / "stl"
RENDER_DIR = REPO_ROOT / "renders"
DOCS_DIR = REPO_ROOT / "docs"
FEM_DIR = REPO_ROOT / "fem"
BUILD_DIR = REPO_ROOT / "build"

#: Image size and camera options passed to PythonSCAD for every render.
RENDER_OPTIONS = (
    "--imgsize=1600,1200",
    "--autocenter",
    "--viewall",
    "--projection=p",
    "--colorscheme=Tomorrow",
)

#: Inspection views: name → camera rotation (x, y, z in degrees, OpenSCAD convention; the
#: distance and center come from ``--viewall`` / ``--autocenter``). The first is the normal view.
INSPECT_VIEWS: dict[str, tuple[float, float, float]] = {
    "iso": (55, 0, 25),
    "iso_rear": (55, 0, 205),
    "front": (90, 0, 0),
    "rear": (90, 0, 180),
    "left": (90, 0, 90),
    "right": (90, 0, 270),
    "top": (0, 0, 0),
}


def check() -> None:
    """Run the design checks and print the key numbers."""
    from plotzker.assemblies.skeleton import clearance_report

    params.check_design()
    typer.echo(params.report())
    typer.echo(clearance_report())
    typer.secho("Design checks passed.", fg=typer.colors.GREEN)


def export_stls(names: Iterable[str] | None = None, out_dir: Path = STL_DIR) -> list[Path]:
    """Export printable parts as STL; returns the written paths."""
    from pythonscad import export

    from plotzker.parts import PRINTABLE_PARTS

    params.check_design()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in _select(names, PRINTABLE_PARTS):
        path = out_dir / f"{name}.stl"
        export(PRINTABLE_PARTS[name](), str(path))
        typer.echo(
            f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}"
        )
        written.append(path)
    return written


def export_layout(out_dir: Path = DOCS_DIR) -> list[Path]:
    """Write the 1:1 baseboard drilling layout (SVG + hole table); returns the paths."""
    from plotzker.layout import write_layout

    params.check_design()
    written = write_layout(out_dir)
    for path in written:
        typer.echo(
            f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}"
        )
    return written


def find_pythonscad(explicit: str | None = None) -> str:
    """Locate the PythonSCAD application binary."""
    candidates = [
        explicit,
        os.environ.get("PYTHONSCAD"),
        shutil.which("pythonscad"),
        "/Applications/PythonSCAD.app/Contents/MacOS/PythonSCAD",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError(
        "PythonSCAD binary not found: install the app, put `pythonscad` on the PATH, "
        "or pass --pythonscad / set $PYTHONSCAD."
    )


def render_pngs(
    names: Iterable[str] | None = None,
    out_dir: Path = RENDER_DIR,
    binary: str | None = None,
    inspect: bool = False,
) -> list[Path]:
    """Render parts and assemblies to PNG with the PythonSCAD application.

    One normal view per name (``renders/<name>.png``), or with ``inspect`` every view of
    ``INSPECT_VIEWS`` (``renders/inspect/<name>_<view>.png``) for checking a change from
    all sides.
    """
    from plotzker.assemblies import ASSEMBLIES
    from plotzker.parts import PRINTABLE_PARTS

    exe = find_pythonscad(binary)
    targets = {
        **{n: "parts:PRINTABLE_PARTS" for n in PRINTABLE_PARTS},
        **{n: "assemblies:ASSEMBLIES" for n in ASSEMBLIES},
    }
    views: dict[str, tuple[float, float, float] | None]
    if inspect:
        out_dir = out_dir / "inspect"
        views = dict(INSPECT_VIEWS)
    else:
        views = {"": None}
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with tempfile.TemporaryDirectory() as tmp:
        for name in _select(names, targets):
            module, registry = targets[name].split(":")
            driver = Path(tmp) / f"{name}.py"
            driver.write_text(
                textwrap.dedent(
                    f"""\
                    import sys
                    sys.path.insert(0, {str(SRC_DIR)!r})
                    from pythonscad import show
                    from plotzker.{module} import {registry}
                    show({registry}[{name!r}]())
                    """
                )
            )
            for view, rotation in views.items():
                path = out_dir / (f"{name}_{view}.png" if view else f"{name}.png")
                cmd = [exe, "--trust-python", "-o", str(path), *RENDER_OPTIONS]
                if rotation:
                    cmd.append(f"--camera=0,0,0,{','.join(f'{a:g}' for a in rotation)},500")
                cmd.append(str(driver))
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if result.returncode != 0 or not path.exists():
                    raise RuntimeError(
                        f"Render of {name} {view} failed:\n{result.stdout}\n{result.stderr}"
                    )
                shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
                typer.echo(f"wrote {shown}")
                written.append(path)
    return written


def _select(names: Iterable[str] | None, available: Collection[str]) -> list[str]:
    """Validate ``names`` against ``available``; default to all of them."""
    if not names:
        return list(available)
    unknown = [n for n in names if n not in available]
    if unknown:
        raise SystemExit(
            f"Unknown name(s): {', '.join(unknown)}. Available: {', '.join(available)}"
        )
    return list(names)


def _fem_status(check_geometry: bool) -> None:
    """Print the FEM state of every printable part."""
    from plotzker.fem.assembly import assembly_status_lines
    from plotzker.fem.report import status_lines
    from plotzker.parts import PARTS, PRINTABLE_PARTS

    verdicts = FEM_DIR / "verdicts.toml"
    from plotzker.assembly_checks import ASSEMBLY_CHECKS

    lines = status_lines(list(PRINTABLE_PARTS), PARTS, verdicts, check_geometry)
    print("\n".join(lines + assembly_status_lines(ASSEMBLY_CHECKS, PARTS, verdicts)))


class Refine(StrEnum):
    """When ``fem`` solves a finer second mesh."""

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


def _run_fem(
    names: Iterable[str],
    out: Path,
    size: float | None,
    refine: Refine,
    uniform: bool,
    solver: str,
    viz: bool,
    record: bool,
) -> bool:
    """Run the FEM checks; True if every one is a PASS or MARGINAL."""
    from plotzker.assembly_checks import ASSEMBLY_CHECKS
    from plotzker.fem.assembly import run_assemblies
    from plotzker.fem.runner import RunOptions, run_checks
    from plotzker.parts import PARTS

    options = RunOptions(size, refine.value, not uniform, solver, viz)
    part_names = [n for n in names if n not in ASSEMBLY_CHECKS]
    verdicts = FEM_DIR / "verdicts.toml"
    results = run_checks(part_names, out, verdicts, options, record=record)
    statuses = [r.status.value for r in results]
    # an assembly is judged from its members' results, so after them
    wanted = [n for n in names if n in ASSEMBLY_CHECKS]
    wanted += [
        a.name
        for a in ASSEMBLY_CHECKS.values()
        if a.name not in wanted and part_names and set(a.members) <= set(part_names)
    ]
    statuses += [
        r.status.value for r in run_assemblies(wanted, PARTS, out, verdicts, record=record)
    ]
    return all(s in ("PASS", "MARGINAL") for s in statuses)


def _serve(folder: Path, port: int) -> None:
    """Serve a report folder on localhost until interrupted, and open it in the browser."""
    import http.server
    import webbrowser

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        typer.echo(f"serving {folder.name} at {url} (Ctrl-C to stop)")
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            typer.echo()


app = typer.Typer(
    name="plotzker",
    help=(__doc__ or "").split("\n\n")[0],
    no_args_is_help=True,
    add_completion=False,
)

OutDir = Annotated[Path, typer.Option(help="Output folder.")]
PythonscadBinary = Annotated[
    str | None, typer.Option("--pythonscad", help="Path to the PythonSCAD binary.")
]


def _reports_errors[**P](command: Callable[P, None]) -> Callable[P, None]:
    """Print a build error (bad design, missing tool, failed step) and exit with code 1."""

    @functools.wraps(command)
    def run(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            command(*args, **kwargs)
        except (params.DesignError, FileNotFoundError, RuntimeError, ValueError) as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from exc

    return run


@app.command("check")
@_reports_errors
def check_command() -> None:
    """Run the design checks and print the key numbers."""
    check()


@app.command("stl")
@_reports_errors
def stl_command(
    names: Annotated[list[str] | None, typer.Argument(help="Part names (default: all).")] = None,
    out: OutDir = STL_DIR,
) -> None:
    """Export printable parts to STL."""
    export_stls(names, out)


@app.command("render")
@_reports_errors
def render_command(
    names: Annotated[
        list[str] | None, typer.Argument(help="Part or assembly names (default: all).")
    ] = None,
    out: OutDir = RENDER_DIR,
    inspect: Annotated[
        bool,
        typer.Option(
            help="Render all views (iso, rear iso, front, rear, left, right, top) "
            "to renders/inspect/."
        ),
    ] = False,
    pythonscad: PythonscadBinary = None,
) -> None:
    """Render parts and assemblies to PNG (needs PythonSCAD)."""
    render_pngs(names, out, pythonscad, inspect)


@app.command("part")
@_reports_errors
def part_command(
    name: Annotated[str | None, typer.Argument(help="Part name.")] = None,
    list_all: Annotated[bool, typer.Option("--list", help="List all parts.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print as JSON.")] = False,
    stl: Annotated[
        Path | None, typer.Option(help="Write the part (analysis frame) to this STL file.")
    ] = None,
) -> None:
    """Show a part's print profile, material and FEM properties."""
    from plotzker import part_report

    if stl is not None and name:
        part_report.export_part_stl(name, stl)
    elif list_all or not name:
        typer.echo(part_report.list_parts())
    else:
        typer.echo(part_report.part_json(name) if as_json else part_report.part_text(name))


@app.command("fem")
@_reports_errors
def fem_command(
    names: Annotated[
        list[str],
        typer.Argument(
            help="Part names, or assembly names (judged from the members' recorded results; "
            "assemblies whose members were all just checked are included)."
        ),
    ],
    size: Annotated[
        float | None, typer.Option(help="Element size near loads in mm (default by size).")
    ] = None,
    refine: Annotated[
        Refine,
        typer.Option(help="Solve a finer second mesh: only near a limit, always, or never."),
    ] = Refine.AUTO,
    uniform: Annotated[bool, typer.Option(help="Same element size everywhere.")] = False,
    solver: Annotated[str, typer.Option(help="CalculiX solver (default: SPOOLES).")] = "",
    viz: Annotated[bool, typer.Option(help="Also write pictures and .vtu files.")] = False,
    no_record: Annotated[
        bool,
        typer.Option(
            "--no-record",
            help="Diagnostic run: leave fem/verdicts.toml alone (use --out to keep results apart).",
        ),
    ] = False,
    out: OutDir = FEM_DIR / "results",
) -> None:
    """FEM check of parts (needs FreeCAD's gmsh and CalculiX); exit code 1 unless all pass."""
    if not _run_fem(names, out, size, refine, uniform, solver, viz, record=not no_record):
        raise typer.Exit(1)


@app.command("fem-status")
@_reports_errors
def fem_status_command(
    no_geometry: Annotated[
        bool, typer.Option("--no-geometry", help="Skip the geometry hash (spec changes only).")
    ] = False,
) -> None:
    """Show the FEM state of every part; stale verdicts are flagged."""
    _fem_status(not no_geometry)


@app.command("diff")
@_reports_errors
def diff_command(
    rev_a: Annotated[str, typer.Argument(help="Base revision.")] = "HEAD",
    rev_b: Annotated[str, typer.Argument(help="Revision to compare (default: working tree).")] = (
        "WORKTREE"
    ),
    all_parts: Annotated[bool, typer.Option("--all", help="Also list unchanged parts.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the comparison as JSON.")] = False,
    open_report: Annotated[
        bool, typer.Option("--open", help="Open the HTML report in the browser.")
    ] = False,
    serve: Annotated[bool, typer.Option(help="Serve the report on localhost.")] = False,
    port: Annotated[int, typer.Option(help="Port for --serve.")] = 8765,
    no_html: Annotated[bool, typer.Option("--no-html", help="Skip the HTML report.")] = False,
    out: OutDir = BUILD_DIR / "diff",
) -> None:
    """Show the parts added, removed or changed between two git revisions."""
    from plotzker.diff.assembly import compare_assemblies, format_assemblies
    from plotzker.diff.compare import compare_snapshots, format_report, to_json
    from plotzker.diff.report import write_report
    from plotzker.diff.snapshot import take_snapshot
    from plotzker.diff.source import collect, format_source

    a = take_snapshot(REPO_ROOT, rev_a, out / "snapshots")
    b = take_snapshot(REPO_ROOT, rev_b, out / "snapshots")
    changes = compare_snapshots(a, b)
    volumes = {c.name: (c.after or c.before).volume for c in changes if c.after or c.before}  # type: ignore[union-attr]
    assemblies = compare_assemblies(a, b, volumes)
    changed = [c.name for c in changes if c.status.value not in ("unchanged", "error")]
    info = collect(REPO_ROOT, a, b, changed)
    if as_json:
        typer.echo(to_json(a, b, changes, assemblies))
    else:
        typer.echo(format_report(a, b, changes, all_parts))
        typer.echo()
        typer.echo(format_assemblies(assemblies, all_parts))
        if text := format_source(info):
            typer.echo()
            typer.echo(text)
    if not no_html:
        report = write_report(a, b, changes, out / "reports", assemblies, info)
        typer.echo(f"\nreport: {report}", err=as_json)
        if serve:
            _serve(report.parent, port)
        elif open_report:
            import webbrowser

            webbrowser.open(report.as_uri())


@app.command("freecad")
@_reports_errors
def freecad_command() -> None:
    """Export the machine components for the FreeCAD assembly."""
    from plotzker.freecad_export import export_freecad

    export_freecad()


@app.command("layout")
@_reports_errors
def layout_command(out: OutDir = DOCS_DIR) -> None:
    """Write the baseboard drilling layout (SVG + table)."""
    export_layout(out)


@app.command("all")
@_reports_errors
def all_command(pythonscad: PythonscadBinary = None) -> None:
    """Run check, stl, render and layout."""
    check()
    export_stls()
    export_layout()
    render_pngs(binary=pythonscad)


def main() -> None:
    """Command-line entry point (``plotzker`` and ``python -m plotzker``)."""
    app(prog_name="python -m plotzker")
