"""Exports of a project: STL files of its parts and PNG renders of parts and assemblies.

STL export uses the ``pythonscad`` Python module. PNG rendering needs the PythonSCAD
application (``pythonscad`` on the PATH, ``$PYTHONSCAD`` or an explicit path): the pip module
has no image export.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
from collections.abc import Callable, Collection, Iterable
from pathlib import Path

from cadder.project import Project

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


def shown(project: Project, path: Path) -> Path:
    """``path`` relative to the project root when it is inside it (for messages)."""
    return path.relative_to(project.root) if path.is_relative_to(project.root) else path


def select(names: Iterable[str] | None, available: Collection[str]) -> list[str]:
    """Validate ``names`` against ``available``; default to all of them."""
    if not names:
        return list(available)
    unknown = [n for n in names if n not in available]
    if unknown:
        raise SystemExit(
            f"Unknown name(s): {', '.join(unknown)}. Available: {', '.join(available)}"
        )
    return list(names)


def export_stls(
    project: Project,
    names: Iterable[str] | None = None,
    out_dir: Path | None = None,
    log: Callable[[str], None] = print,
) -> list[Path]:
    """Export the project's parts as STL (default: all with ``stl`` set); returns the paths."""
    from pythonscad import export

    project.check_design()
    parts = project.parts()
    out_dir = out_dir or project.path("stl")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in select(names, [n for n, p in parts.items() if p.stl]):
        path = out_dir / f"{name}.stl"
        export(parts[name].build(), str(path))
        log(f"wrote {shown(project, path)}")
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
    project: Project,
    names: Iterable[str] | None = None,
    out_dir: Path | None = None,
    binary: str | None = None,
    inspect: bool = False,
    log: Callable[[str], None] = print,
) -> list[Path]:
    """Render parts and assemblies to PNG with the PythonSCAD application.

    One normal view per name (``<renders>/<name>.png``), or with ``inspect`` every view of
    ``INSPECT_VIEWS`` (``<renders>/inspect/<name>_<view>.png``) for checking a change from
    all sides.
    """
    exe = find_pythonscad(binary)
    targets = [*project.parts(), *project.assemblies()]
    out_dir = out_dir or project.path("renders")
    views: dict[str, tuple[float, float, float] | None]
    if inspect:
        out_dir = out_dir / "inspect"
        views = dict(INSPECT_VIEWS)
    else:
        views = {"": None}
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [str(project.root / d) for d in project.source_dirs]
    written = []
    with tempfile.TemporaryDirectory() as tmp:
        for name in select(names, targets):
            driver = Path(tmp) / f"{name}.py"
            driver.write_text(
                textwrap.dedent(
                    f"""\
                    import sys
                    sys.path[0:0] = {paths!r}
                    from pythonscad import show
                    from cadder.project import load_project
                    project = load_project({project.spec!r})
                    show({{**project.parts(), **project.assemblies()}}[{name!r}].build())
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
                log(f"wrote {shown(project, path)}")
                written.append(path)
    return written
