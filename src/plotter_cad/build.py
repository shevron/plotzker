"""Build outputs: design checks, STL export and PNG renders.

Usage (from the repository root, with the package installed or ``src`` on the path)::

    python -m plotter_cad check            # design checks + key numbers
    python -m plotter_cad stl              # all printable parts → stl/
    python -m plotter_cad stl x_carriage   # one part
    python -m plotter_cad render           # parts + assemblies → renders/*.png
    python -m plotter_cad all              # check, stl, render

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
from collections.abc import Iterable, Sequence
from pathlib import Path

from plotter_cad import params

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = Path(__file__).resolve().parents[1]
STL_DIR = REPO_ROOT / "stl"
RENDER_DIR = REPO_ROOT / "renders"

#: Image size and camera options passed to PythonSCAD for every render.
RENDER_OPTIONS = (
    "--imgsize=1600,1200",
    "--autocenter",
    "--viewall",
    "--projection=p",
    "--colorscheme=Tomorrow",
)


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
    names: Iterable[str] | None = None, out_dir: Path = RENDER_DIR, binary: str | None = None
) -> list[Path]:
    """Render parts and assemblies to PNG with the PythonSCAD application."""
    from plotter_cad.assemblies import ASSEMBLIES
    from plotter_cad.parts import PRINTABLE_PARTS

    exe = find_pythonscad(binary)
    targets = {
        **{n: "parts:PRINTABLE_PARTS" for n in PRINTABLE_PARTS},
        **{n: "assemblies:ASSEMBLIES" for n in ASSEMBLIES},
    }
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
            path = out_dir / f"{name}.png"
            cmd = [exe, "--trust-python", "-o", str(path), *RENDER_OPTIONS, str(driver)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0 or not path.exists():
                raise RuntimeError(f"Render of {name} failed:\n{result.stdout}\n{result.stderr}")
            print(
                f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}"
            )
            written.append(path)
    return written


def _select(names: Iterable[str] | None, available: dict) -> list[str]:
    if not names:
        return list(available)
    unknown = [n for n in names if n not in available]
    if unknown:
        raise SystemExit(
            f"Unknown name(s): {', '.join(unknown)}. Available: {', '.join(available)}"
        )
    return list(names)


def main(argv: Sequence[str] | None = None) -> int:
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
    render.add_argument("--pythonscad", help="path to the PythonSCAD binary")
    everything = sub.add_parser("all", help="check, stl and render")
    everything.add_argument("--pythonscad", help="path to the PythonSCAD binary")
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            check()
        elif args.command == "stl":
            export_stls(args.names, args.out)
        elif args.command == "render":
            render_pngs(args.names, args.out, args.pythonscad)
        else:
            check()
            export_stls()
            render_pngs(binary=args.pythonscad)
    except (params.DesignError, FileNotFoundError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
