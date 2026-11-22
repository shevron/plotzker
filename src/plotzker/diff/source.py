"""What changed in the source between two revisions: commits, files, per-part diffs, FEM hints.

Everything here asks git. ``WORKTREE`` stands for the files on disk (``git diff`` against it
shows tracked files only; a new untracked module appears when it is added to git).
"""

import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plotzker.diff.snapshot import WORKTREE, Snapshot

#: Source diffs longer than this many lines are cut (the viewer says so).
MAX_DIFF_LINES = 400
#: The shared parameter module, whose changes explain most part changes.
PARAMS_PATH = "src/plotzker/params.py"
SOURCE_ROOT = "src/plotzker"


@dataclass(frozen=True)
class FileChange:
    """A source file that differs between the revisions."""

    path: str
    added: int
    deleted: int


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _diff_args(a: str, b: str) -> list[str] | None:
    """The ``git diff`` arguments that compare commit/WORKTREE ``a`` with ``b`` (None: same)."""
    if a == b:
        return None
    if b == WORKTREE:
        return [a]
    if a == WORKTREE:
        return ["-R", b]
    return [a, b]


def commit_log(repo: Path, a: str, b: str) -> list[str]:
    """One line per commit going from ``a`` to ``b`` (newest first); empty if not linear."""
    if WORKTREE in (a, b):
        a, b = (a if a != WORKTREE else "HEAD"), (b if b != WORKTREE else "HEAD")
    if a == b:
        return []
    try:
        out = _git(repo, "log", "--format=%h %s", f"{a}..{b}")
    except RuntimeError:
        return []
    return out.splitlines()


def changed_files(repo: Path, a: str, b: str) -> list[FileChange]:
    """Source files under ``src/plotzker`` that differ, with added/deleted line counts."""
    args = _diff_args(a, b)
    if args is None:
        return []
    out = _git(repo, "diff", "--numstat", *args, "--", SOURCE_ROOT)
    files = []
    for line in out.splitlines():
        added, deleted, path = line.split("\t", 2)
        if added != "-":
            files.append(FileChange(path, int(added), int(deleted)))
    return files


def file_diff(repo: Path, a: str, b: str, path: str) -> str:
    """The unified diff of one file (cut to :data:`MAX_DIFF_LINES` lines), or ''."""
    args = _diff_args(a, b)
    if args is None or not path:
        return ""
    lines = _git(repo, "diff", "--no-color", "-U3", *args, "--", path).splitlines()
    # drop the "diff --git / index / ---/+++" header: the viewer shows the path itself
    body = [ln for ln in lines if not ln.startswith(("diff --git", "index ", "--- ", "+++ "))]
    if len(body) > MAX_DIFF_LINES:
        body = [*body[:MAX_DIFF_LINES], f"… {len(body) - MAX_DIFF_LINES} more lines"]
    return "\n".join(body)


def _verdicts(repo: Path, rev: str) -> dict[str, dict[str, Any]]:
    """``fem/verdicts.toml`` as of ``rev`` ({} if it has none)."""
    try:
        if rev == WORKTREE:
            text = (repo / "fem" / "verdicts.toml").read_text()
        else:
            text = _git(repo, "show", f"{rev}:fem/verdicts.toml")
        return tomllib.loads(text)
    except OSError, RuntimeError, tomllib.TOMLDecodeError:
        return {}


def fem_hints(repo: Path, a: str, b: str, changed: list[str]) -> dict[str, str]:
    """A one-line FEM note for each changed part that has a verdict in either revision.

    "re-checked" if the verdict entry differs between the revisions; "not re-run" if the part
    changed but its entry did not (the verdict may be stale: ``make fem-status`` tells).
    """
    va, vb = _verdicts(repo, a), _verdicts(repo, b)
    hints = {}
    for name in changed:
        ea, eb = va.get(name), vb.get(name)
        if ea is None and eb is None:
            continue
        if ea == eb:
            hints[name] = f"verdict {eb['verdict'] if eb else '?'} not re-run since this change"
        elif ea is None and eb is not None:
            hints[name] = f"first verdict {eb['verdict']}"
        elif eb is None and ea is not None:
            hints[name] = f"verdict {ea['verdict']} removed"
        elif ea is not None and eb is not None:
            hints[name] = f"re-checked {ea['verdict']} → {eb['verdict']}"
    return hints


def collect(repo: Path, a: Snapshot, b: Snapshot, changed_parts: list[str]) -> dict[str, Any]:
    """Source information for the report: ``{"log", "files", "params", "parts": {name: {...}}}``."""
    parts: dict[str, dict[str, str]] = {}
    hints = fem_hints(repo, a.commit, b.commit, changed_parts)
    for name in changed_parts:
        pf = b.parts.get(name) or a.parts.get(name)
        path = pf.source if pf and pf.source else ""
        info = {"path": path, "diff": file_diff(repo, a.commit, b.commit, path)}
        if name in hints:
            info["fem"] = hints[name]
        parts[name] = info
    return {
        "log": commit_log(repo, a.commit, b.commit),
        "files": [
            {"path": f.path, "added": f.added, "deleted": f.deleted}
            for f in changed_files(repo, a.commit, b.commit)
        ],
        "params": file_diff(repo, a.commit, b.commit, PARAMS_PATH),
        "parts": parts,
    }


def format_source(info: dict[str, Any]) -> str:
    """Text summary of :func:`collect`: commits, changed files and FEM notes."""
    lines = []
    if info["log"]:
        lines.append(f"Commits ({len(info['log'])}):")
        lines += [f"  {ln}" for ln in info["log"][:15]]
        if len(info["log"]) > 15:
            lines.append(f"  … {len(info['log']) - 15} more")
    if info["files"]:
        lines.append("Source files changed:")
        lines += [f"  +{f['added']:<4} -{f['deleted']:<4} {f['path']}" for f in info["files"]]
    notes = [(n, p["fem"]) for n, p in info["parts"].items() if "fem" in p]
    if notes:
        lines.append("FEM:")
        lines += [f"  {n:<28} {note}" for n, note in notes]
    return "\n".join(lines)
