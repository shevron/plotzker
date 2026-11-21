"""Build the printable parts of one revision (a git commit or the working tree).

A commit is checked out into a temporary ``git worktree`` and built in a subprocess with that
tree's own ``src/`` on the path, so two revisions never share one interpreter. Results are cached
by commit hash in ``build/diff/snapshots/``; the working tree is rebuilt every time.
"""

import json
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

#: Name of the revision that means "the files on disk right now".
WORKTREE = "WORKTREE"

_DRIVER = textwrap.dedent(
    """\
    import inspect, json, sys, traceback
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    result = {"parts": {}, "error": None, "version": 2}
    try:
        from pythonscad import export
        from plotter_cad.parts import PRINTABLE_PARTS
        import plotter_cad
        here = Path(plotter_cad.__file__).resolve()
        if not here.is_relative_to(Path(sys.argv[1]).resolve()):
            raise ImportError("revision has no plotter_cad package; imported " + str(here))
    except Exception:
        result["error"] = traceback.format_exc()
        PRINTABLE_PARTS = {}
    for name, build in PRINTABLE_PARTS.items():
        try:
            export(build(), str(out / (name + ".stl")))
            try:
                root = Path(sys.argv[1]).resolve().parent
                src = str(Path(inspect.getsourcefile(build)).resolve().relative_to(root))
            except Exception:
                src = None
            result["parts"][name] = {"file": name + ".stl", "error": None, "source": src}
        except Exception:
            result["parts"][name] = {"file": None, "error": traceback.format_exc(limit=3)}
    result["assemblies"] = {}
    try:
        import numpy as np
        from plotter_cad.assemblies import ASSEMBLIES
    except Exception:
        ASSEMBLIES = {}
    for name, build in ASSEMBLIES.items():
        try:
            arrays = {}
            for i, item in enumerate(build()):
                verts, faces = item.mesh()
                # faces may be polygons: fan-triangulate them
                tri = [(f[0], f[k], f[k + 1]) for f in faces for k in range(1, len(f) - 1)]
                if tri:
                    arrays["i%d" % i] = np.asarray(verts, dtype=np.float32)[np.asarray(tri)]
            np.savez(out / ("asm_" + name + ".npz"), **arrays)
            result["assemblies"][name] = {"file": "asm_" + name + ".npz", "error": None}
        except Exception:
            result["assemblies"][name] = {"file": None, "error": traceback.format_exc(limit=3)}
    (out / "parts.json").write_text(json.dumps(result, indent=1))
    """
)


@dataclass(frozen=True)
class PartFile:
    """One built part: its STL (or why there is none)."""

    path: Path | None
    error: str | None = None
    source: str | None = None  #: the module that defines it, relative to the repository root


@dataclass
class Snapshot:
    """The printable parts of one revision."""

    label: str  #: what the user asked for ("HEAD", "main~3", "WORKTREE")
    commit: str  #: full hash, or ``WORKTREE``
    parts: dict[str, PartFile] = field(default_factory=dict)
    assemblies: dict[str, PartFile] = field(default_factory=dict)  #: path is an .npz of items
    error: str | None = None  #: the revision could not be built at all


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def resolve(repo: Path, rev: str) -> str:
    """The commit hash of ``rev``, or ``WORKTREE``."""
    if rev == WORKTREE:
        return WORKTREE
    return _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}")


def _build(tree: Path, out_dir: Path) -> Snapshot:
    """Run the driver in ``tree`` and read back its manifest."""
    with tempfile.TemporaryDirectory() as tmp:
        driver = Path(tmp) / "driver.py"
        driver.write_text(_DRIVER)
        # -I would ignore PYTHONPATH; the driver puts the tree's src first on sys.path instead.
        proc = subprocess.run(
            [sys.executable, str(driver), str(tree / "src"), str(out_dir)],
            cwd=tree,
            capture_output=True,
            text=True,
            check=False,
        )
    if not (out_dir / "parts.json").exists():
        return Snapshot(label="", commit="", error=f"build failed:\n{proc.stdout}\n{proc.stderr}")
    return _read_manifest(out_dir)


def _read_manifest(out: Path) -> Snapshot:
    data = json.loads((out / "parts.json").read_text())
    snap = Snapshot(label="", commit="", error=data["error"])
    for name, entry in data["parts"].items():
        file = out / entry["file"] if entry["file"] else None
        snap.parts[name] = PartFile(file, entry["error"], entry.get("source"))
    for name, entry in data.get("assemblies", {}).items():
        file = out / entry["file"] if entry["file"] else None
        snap.assemblies[name] = PartFile(file, entry["error"])
    return snap


def take_snapshot(repo: Path, rev: str, cache_dir: Path) -> Snapshot:
    """Build all printable parts of ``rev`` (cached for commits)."""
    commit = resolve(repo, rev)
    if commit == WORKTREE:
        out = cache_dir / WORKTREE
        if out.exists():
            for old in out.glob("*"):
                old.unlink()
        snap = _build(repo, out)
    else:
        out = cache_dir / commit
        if (out / "parts.json").exists() and json.loads((out / "parts.json").read_text()).get(
            "version", 1
        ) >= 2:
            snap = _read_manifest(out)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                tree = Path(tmp) / "tree"
                _git(repo, "worktree", "add", "--detach", str(tree), commit)
                try:
                    snap = _build(tree, out)
                finally:
                    _git(repo, "worktree", "remove", "--force", str(tree))
    snap.label, snap.commit = rev, commit
    return snap
