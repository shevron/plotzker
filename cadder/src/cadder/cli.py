"""The ``cadder`` command line: checks, exports, reports, FEM and the design diff of a project.

Usage (from the project's repository; the project is ``[tool.cadder] project`` in the nearest
``pyproject.toml``, or ``--project package.module:PROJECT`` before the command)::

    cadder check                 # design checks + key numbers
    cadder stl [NAMES]           # parts → stl/
    cadder render [NAMES]        # parts + assemblies → renders/*.png (PythonSCAD app)
    cadder render --inspect      # all views → renders/inspect/<name>_<view>.png
    cadder part --list           # parts with profile, material and FEM state
    cadder part NAME [--json]    # a part's print/FEM properties (--json: for an FEM reviewer)
    cadder fem-status            # FEM state of every part, stale verdicts flagged
    cadder fem NAME...           # FEM check of parts → fem/results/, fem/verdicts.toml
    cadder diff [A [B]]          # parts changed between git revisions
    cadder all                   # check, stl, the project's extra outputs, render
    cadder photo COMMAND         # measure parts from photos (docs/photo.md; the photo extra)

A project adds its own commands (``Project.commands``). The CLI is a Typer app.
"""

import functools
import sys
from collections.abc import Callable, Iterable
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from cadder.checks import DesignError
from cadder.project import Project, find_spec, load_project
from cadder.render import export_stls, render_pngs


def reports_errors[**P](command: Callable[P, None]) -> Callable[P, None]:
    """Print a build error (bad design, missing tool, failed step) and exit with code 1."""

    @functools.wraps(command)
    def run(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            command(*args, **kwargs)
        except (DesignError, FileNotFoundError, RuntimeError, ValueError) as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from exc

    return run


class Refine(StrEnum):
    """When ``fem`` solves a finer second mesh."""

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


OutDir = Annotated[Path | None, typer.Option(help="Output folder.")]
PythonscadBinary = Annotated[str | None, typer.Option("--pythonscad", help="Path to the PythonSCAD binary.")]


def check(project: Project) -> None:
    """Run the design checks and print the key numbers."""
    project.check_design()
    if project.report is not None:
        typer.echo(project.report())
    typer.secho("Design checks passed.", fg=typer.colors.GREEN)


def run_fem(
    project: Project,
    names: Iterable[str],
    out: Path,
    options: object,
    record: bool,
) -> bool:
    """Run the FEM checks of parts and assembly checks; True if every one passes (or is
    marginal)."""
    from cadder.fem.assembly import run_assemblies
    from cadder.fem.runner import RunOptions, run_checks

    assert isinstance(options, RunOptions)
    checks = project.assembly_checks()
    parts = project.material_parts()
    part_names = [n for n in names if n not in checks]
    results = run_checks(parts, part_names, out, project.verdicts, options, record=record)
    statuses = [r.status.value for r in results]
    # an assembly is judged from its members' results, so after them
    wanted = [n for n in names if n in checks]
    wanted += [
        a.name for a in checks.values() if a.name not in wanted and part_names and set(a.members) <= set(part_names)
    ]
    statuses += [r.status.value for r in run_assemblies(checks, wanted, parts, out, project.verdicts, record=record)]
    return all(s in ("PASS", "MARGINAL") for s in statuses)


def fem_status(project: Project, check_geometry: bool) -> list[str]:
    """The FEM state of every part and assembly check."""
    from cadder.fem.assembly import assembly_status_lines
    from cadder.fem.report import status_lines

    parts = project.parts()
    lines = status_lines(list(parts), parts, project.verdicts, check_geometry, project.spec)
    checks = project.assembly_checks()
    return lines + assembly_status_lines(checks, project.material_parts(), project.verdicts)


def serve(folder: Path, port: int) -> None:
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


def diff(
    project: Project,
    rev_a: str,
    rev_b: str,
    all_parts: bool,
    as_json: bool,
    open_report: bool,
    serve_port: int | None,
    html: bool,
    out: Path,
) -> None:
    """Show the parts added, removed or changed between two git revisions."""
    from cadder.diff.assembly import compare_assemblies, format_assemblies
    from cadder.diff.compare import compare_snapshots, format_report, to_json
    from cadder.diff.report import write_report
    from cadder.diff.snapshot import BuildConfig, take_snapshot
    from cadder.diff.source import SourceLayout, collect, format_source

    config = BuildConfig(project.spec, project.source_dirs, project.legacy_specs)
    before = take_snapshot(project.root, rev_a, out / "snapshots", config)
    after = take_snapshot(project.root, rev_b, out / "snapshots", config)
    changes = compare_snapshots(before, after)
    volumes = {c.name: (c.after or c.before).volume for c in changes if c.after or c.before}  # type: ignore[union-attr]
    assemblies = compare_assemblies(before, after, volumes)
    changed = [c.name for c in changes if c.status.value not in ("unchanged", "error")]
    layout = SourceLayout(project.source_dirs, project.params_file, project.verdicts_file)
    info = collect(project.root, before, after, changed, layout)
    if as_json:
        typer.echo(to_json(before, after, changes, assemblies))
    else:
        typer.echo(format_report(before, after, changes, all_parts))
        typer.echo()
        typer.echo(format_assemblies(assemblies, all_parts))
        if text := format_source(info):
            typer.echo()
            typer.echo(text)
    if html:
        report = write_report(before, after, changes, out / "reports", assemblies, info)
        typer.echo(f"\nreport: {report}", err=as_json)
        if serve_port is not None:
            serve(report.parent, serve_port)
        elif open_report:
            import webbrowser

            webbrowser.open(report.as_uri())


def _check_command(ctx: typer.Context) -> None:
    """Run the design checks and print the key numbers."""
    project: Project = ctx.obj
    check(project)


def _stl_command(
    ctx: typer.Context,
    names: Annotated[list[str] | None, typer.Argument(help="Part names (default: all).")] = None,
    out: OutDir = None,
) -> None:
    """Export parts to STL."""
    project: Project = ctx.obj
    export_stls(project, names, out, log=typer.echo)


def _render_command(
    ctx: typer.Context,
    names: Annotated[list[str] | None, typer.Argument(help="Part or assembly names (default: all).")] = None,
    out: OutDir = None,
    inspect: Annotated[
        bool,
        typer.Option(help="Render all views (iso, rear iso, front, rear, left, right, top) to renders/inspect/."),
    ] = False,
    pythonscad: PythonscadBinary = None,
) -> None:
    """Render parts and assemblies to PNG (needs PythonSCAD)."""
    project: Project = ctx.obj
    render_pngs(project, names, out, pythonscad, inspect, log=typer.echo)


def _part_command(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument(help="Part name.")] = None,
    list_all: Annotated[bool, typer.Option("--list", help="List all parts.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print as JSON.")] = False,
    stl: Annotated[Path | None, typer.Option(help="Write the part (analysis frame) to this STL file.")] = None,
) -> None:
    """Show a part's print profile, material and FEM properties."""
    project: Project = ctx.obj
    from cadder import report

    parts = project.parts()
    if stl is not None and name:
        report.export_part_stl(name, stl, parts)
    elif list_all or not name:
        typer.echo(report.list_parts(parts))
    else:
        typer.echo(report.part_json(name, parts) if as_json else report.part_text(name, parts))


def _fem_command(
    ctx: typer.Context,
    names: Annotated[
        list[str],
        typer.Argument(
            help="Part names, or assembly check names (judged from the members' recorded "
            "results; checks whose members were all just checked are included)."
        ),
    ],
    size: Annotated[float | None, typer.Option(help="Element size near loads in mm (default by size).")] = None,
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
            help="Diagnostic run: leave the verdicts file alone (use --out to keep results apart).",
        ),
    ] = False,
    out: OutDir = None,
) -> None:
    """FEM check of parts (needs FreeCAD's gmsh and CalculiX); exit code 1 unless all pass."""
    project: Project = ctx.obj
    from cadder.fem.runner import RunOptions

    options = RunOptions(size, refine.value, not uniform, solver, viz, project.spec)
    folder = out or project.path("fem")
    if not run_fem(project, names, folder, options, record=not no_record):
        raise typer.Exit(1)


def _fem_status_command(
    ctx: typer.Context,
    no_geometry: Annotated[
        bool, typer.Option("--no-geometry", help="Skip the geometry hash (spec changes only).")
    ] = False,
) -> None:
    """Show the FEM state of every part; stale verdicts are flagged."""
    project: Project = ctx.obj
    typer.echo("\n".join(fem_status(project, not no_geometry)))


def _diff_command(
    ctx: typer.Context,
    rev_a: Annotated[str, typer.Argument(help="Base revision.")] = "HEAD",
    rev_b: Annotated[str, typer.Argument(help="Revision to compare (default: working tree).")] = "WORKTREE",
    all_parts: Annotated[bool, typer.Option("--all", help="Also list unchanged parts.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the comparison as JSON.")] = False,
    open_report: Annotated[bool, typer.Option("--open", help="Open the HTML report in the browser.")] = False,
    serve_report: Annotated[bool, typer.Option("--serve", help="Serve the report on localhost.")] = False,
    port: Annotated[int, typer.Option(help="Port for --serve.")] = 8765,
    no_html: Annotated[bool, typer.Option("--no-html", help="Skip the HTML report.")] = False,
    out: OutDir = None,
) -> None:
    """Show the parts added, removed or changed between two git revisions."""
    project: Project = ctx.obj
    folder = out or project.path("build") / "diff"
    port_or_none = port if serve_report else None
    diff(
        project,
        rev_a,
        rev_b,
        all_parts,
        as_json,
        open_report,
        port_or_none,
        not no_html,
        folder,
    )


def _freecad_command(
    ctx: typer.Context,
    names: Annotated[list[str] | None, typer.Argument(help="FreeCAD assembly names (default: all).")] = None,
    export_only: Annotated[bool, typer.Option("--export-only", help="Write STLs and manifest, skip FreeCAD.")] = False,
    out: OutDir = None,
) -> None:
    """Build the project's FreeCAD assemblies (needs FreeCAD 1.x for the build step)."""
    project: Project = ctx.obj
    from cadder.freecad.export import build_assembly, export_assembly
    from cadder.render import select

    assemblies = project.freecad_assemblies()
    folder = out or project.path("freecad")
    for name in select(names, assemblies):
        manifest = export_assembly(assemblies[name], folder, log=typer.echo)
        if not export_only:
            build_assembly(manifest, log=typer.echo)


def _all_command(ctx: typer.Context, pythonscad: PythonscadBinary = None) -> None:
    """Run check, stl, the project's extra outputs and render."""
    project: Project = ctx.obj
    check(project)
    export_stls(project, log=typer.echo)
    for step in project.all_steps:
        step()
    render_pngs(project, binary=pythonscad, log=typer.echo)


#: The commands every project has, in the order the help lists them
_COMMANDS: tuple[tuple[str, Callable[..., None]], ...] = (
    ("check", _check_command),
    ("stl", _stl_command),
    ("render", _render_command),
    ("part", _part_command),
    ("fem", _fem_command),
    ("fem-status", _fem_status_command),
    ("diff", _diff_command),
    ("freecad", _freecad_command),
    ("all", _all_command),
)


def make_app(project: Project, prog_name: str = "cadder") -> typer.Typer:
    """The command-line app for ``project``, with its own commands added."""
    app = typer.Typer(
        name=prog_name,
        help=f"cadder for {project.name}: checks, exports, reports, FEM and the design diff.",
        no_args_is_help=True,
        add_completion=False,
        context_settings={"obj": project},  # how the commands get the project
    )

    for name, command in _COMMANDS:
        app.command(name)(reports_errors(command))

    from cadder.photo.cli import app as photo_app  # imports OpenCV only when a command runs

    app.add_typer(photo_app, name="photo")

    if project.commands is not None:
        project.commands(app)
    return app


def run(project: Project, args: list[str] | None = None, prog_name: str = "cadder") -> None:
    """Run the app of ``project`` on ``args`` (default: the command line)."""
    make_app(project, prog_name)(args=args, prog_name=prog_name)


def main() -> None:
    """Entry point of ``cadder`` / ``python -m cadder``: ``[--project SPEC] COMMAND ...``."""
    args = sys.argv[1:]
    spec = None
    if args[:1] == ["--project"] and len(args) > 1:
        spec, args = args[1], args[2:]
    elif args and args[0].startswith("--project="):
        spec, args = args[0].split("=", 1)[1], args[1:]
    spec = spec or find_spec()
    if not spec:
        typer.secho(
            "No project: pass --project package.module:PROJECT or set [tool.cadder] project in pyproject.toml.",
            fg=typer.colors.RED,
            err=True,
        )
        raise SystemExit(2)
    run(load_project(spec), args)
