"""Build outputs: design checks, STL export and PNG renders.

Usage (from the repository root, with the package installed or ``src`` on the path)::

    python -m plotter_cad check            # design checks + key numbers
    python -m plotter_cad stl              # all printable parts → stl/
    python -m plotter_cad stl x_carriage   # one part
    python -m plotter_cad render           # parts + assemblies → renders/*.png
    python -m plotter_cad render --inspect # all views → renders/inspect/<name>_<view>.png
    python -m plotter_cad part --list      # parts with profile, material and FEM state
    python -m plotter_cad part NAME [--json]  # a part's print/FEM properties (--json: sub-agent)
    python -m plotter_cad fem-status       # FEM state of every part, stale verdicts flagged
    python -m plotter_cad fem NAME...      # FEM check of parts → fem/results/, fem/verdicts.toml
    python -m plotter_cad layout           # baseboard drilling layout → docs/
    python -m plotter_cad freecad          # machine components for the FreeCAD assembly → freecad/
    python -m plotter_cad all              # check, stl, render, layout

STL export uses the ``pythonscad`` Python module. PNG rendering needs the PythonSCAD
application (``pythonscad`` on the PATH, or ``--pythonscad PATH`` / ``$PYTHONSCAD``):
the pip module has no image export.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path

from plotter_cad import params

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = Path(__file__).resolve().parents[1]
STL_DIR = REPO_ROOT / "stl"
RENDER_DIR = REPO_ROOT / "renders"
DOCS_DIR = REPO_ROOT / "docs"
FEM_DIR = REPO_ROOT / "fem"

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
    from plotter_cad.assemblies.skeleton import clearance_report

    params.check_design()
    print(params.report())
    print(clearance_report())
    print("Design checks passed.")


def export_stls(names: Iterable[str] | None = None, out_dir: Path = STL_DIR) -> list[Path]:
    """Export printable parts as STL; returns the written paths."""
    from pythonscad import export

    from plotter_cad.parts import PRINTABLE_PARTS

    params.check_design()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in _select(names, PRINTABLE_PARTS):
        path = out_dir / f"{name}.stl"
        export(PRINTABLE_PARTS[name](), str(path))
        print(f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
        written.append(path)
    return written


def export_layout(out_dir: Path = DOCS_DIR) -> list[Path]:
    """Write the 1:1 baseboard drilling layout (SVG + hole table); returns the paths."""
    from plotter_cad.layout import write_layout

    params.check_design()
    written = write_layout(out_dir)
    for path in written:
        print(f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
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
    from plotter_cad.assemblies import ASSEMBLIES
    from plotter_cad.parts import PRINTABLE_PARTS

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
                    from plotter_cad.{module} import {registry}
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
                print(f"wrote {shown}")
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
    from plotter_cad.fem.report import status_lines
    from plotter_cad.parts import PARTS, PRINTABLE_PARTS

    verdicts = FEM_DIR / "verdicts.toml"
    print("\n".join(status_lines(list(PRINTABLE_PARTS), PARTS, verdicts, check_geometry)))


def _run_fem(names: Iterable[str], out: Path, args: argparse.Namespace) -> int:
    """Run the FEM checks; the exit code is 1 if any is not a PASS or MARGINAL."""
    from plotter_cad.fem.runner import RunOptions, run_checks

    options = RunOptions(args.size, args.refine, not args.uniform, args.solver, args.viz)
    results = run_checks(
        list(names), out, FEM_DIR / "verdicts.toml", options, record=not args.no_record
    )
    return 0 if all(r.status.value in ("PASS", "MARGINAL") for r in results) else 1


def _show_part(name: str | None, list_all: bool, as_json: bool, stl: Path | None) -> None:
    """Print the ``part`` command's output."""
    from plotter_cad import part_report

    if stl is not None and name:
        part_report.export_part_stl(name, stl)
    elif list_all or not name:
        print(part_report.list_parts())
    else:
        print(part_report.part_json(name) if as_json else part_report.part_text(name))


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m plotter_cad", description=__doc__.split("\n\n")[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="run the design checks and print the key numbers")
    stl = sub.add_parser("stl", help="export printable parts to STL")
    stl.add_argument("names", nargs="*", help="part names (default: all)")
    stl.add_argument("--out", type=Path, default=STL_DIR)
    render = sub.add_parser("render", help="render parts and assemblies to PNG (needs PythonSCAD)")
    render.add_argument("names", nargs="*", help="part/assembly names (default: all)")
    render.add_argument("--out", type=Path, default=RENDER_DIR)
    render.add_argument(
        "--inspect",
        action="store_true",
        help="render all views (iso, rear iso, front, rear, left, right, top) to renders/inspect/",
    )
    render.add_argument("--pythonscad", help="path to the PythonSCAD binary")
    part = sub.add_parser("part", help="show a part's print profile, material and FEM properties")
    part.add_argument("name", nargs="?", help="part name")
    part.add_argument("--list", action="store_true", help="list all parts")
    part.add_argument("--json", action="store_true", help="print as JSON")
    part.add_argument("--stl", type=Path, help="write the part (analysis frame) to this STL file")
    fem = sub.add_parser("fem", help="FEM check of parts (needs FreeCAD's gmsh and CalculiX)")
    fem.add_argument("names", nargs="+", help="part names")
    fem.add_argument("--size", type=float, help="element size near loads in mm (default by size)")
    fem.add_argument(
        "--refine",
        choices=["auto", "always", "never"],
        default="auto",
        help="solve a finer second mesh: only near a limit (auto), always, or never",
    )
    fem.add_argument("--uniform", action="store_true", help="same element size everywhere")
    fem.add_argument("--solver", default="", help="CalculiX solver (default: SPOOLES)")
    fem.add_argument("--viz", action="store_true", help="also write pictures and .vtu files")
    fem.add_argument(
        "--no-record",
        action="store_true",
        help="diagnostic run: leave fem/verdicts.toml alone (use --out to keep results apart)",
    )
    fem.add_argument("--out", type=Path, default=FEM_DIR / "results")
    status = sub.add_parser("fem-status", help="FEM state of every part; stale verdicts flagged")
    status.add_argument(
        "--no-geometry", action="store_true", help="skip the geometry hash (spec changes only)"
    )
    sub.add_parser("freecad", help="export the machine components for the FreeCAD assembly")
    layout = sub.add_parser("layout", help="write the baseboard drilling layout (SVG + table)")
    layout.add_argument("--out", type=Path, default=DOCS_DIR)
    everything = sub.add_parser("all", help="check, stl, render and layout")
    everything.add_argument("--pythonscad", help="path to the PythonSCAD binary")
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            check()
        elif args.command == "stl":
            export_stls(args.names, args.out)
        elif args.command == "render":
            render_pngs(args.names, args.out, args.pythonscad, args.inspect)
        elif args.command == "fem-status":
            _fem_status(not args.no_geometry)
        elif args.command == "fem":
            return _run_fem(args.names, args.out, args)
        elif args.command == "part":
            _show_part(args.name, args.list, args.json, args.stl)
        elif args.command == "freecad":
            from plotter_cad.freecad_export import export_freecad

            export_freecad()
        elif args.command == "layout":
            export_layout(args.out)
        else:
            check()
            export_stls()
            export_layout()
            render_pngs(binary=args.pythonscad)
    except (params.DesignError, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
