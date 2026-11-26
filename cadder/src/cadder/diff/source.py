"""What changed in the source between two revisions: commits, files, per-part diffs, FEM hints.

Everything here asks git. ``WORKTREE`` stands for the files on disk (``git diff`` against it
shows tracked files only; a new untracked module appears when it is added to git).
"""

import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cadder.diff.snapshot import WORKTREE, Snapshot

#: Source diffs longer than this many lines are cut (the viewer says so).
MAX_DIFF_LINES = 400


@dataclass(frozen=True)
class SourceLayout:
    """Where a project's source and FEM verdicts are, relative to the repository root."""

    #: folders whose changed files are listed
    roots: tuple[str, ...] = ("src",)
    #: the shared parameter module, whose changes explain most part changes (None: none)
    params_file: str | None = None
    verdicts_file: str = "fem/verdicts.toml"


@dataclass(frozen=True)
class FileChange:
    """A source file that differs between the revisions."""

    path: str
    added: int
    deleted: int


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
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


def commit_log(repo: Path, rev_a: str, rev_b: str) -> list[str]:
    """One line per commit going from ``a`` to ``b`` (newest first); empty if not linear."""
    if WORKTREE in (rev_a, rev_b):
        rev_a, rev_b = (rev_a if rev_a != WORKTREE else "HEAD"), (rev_b if rev_b != WORKTREE else "HEAD")
    if rev_a == rev_b:
        return []
    try:
        out = _git(repo, "log", "--format=%h %s", f"{rev_a}..{rev_b}")
    except RuntimeError:
        return []
    return out.splitlines()


def changed_files(
    repo: Path,
    rev_a: str,
    rev_b: str,
    layout: SourceLayout = SourceLayout(),  # noqa: B008
) -> list[FileChange]:
    """Source files under the layout's roots that differ, with added/deleted line counts (a
    moved file shows as ``old => new``)."""
    args = _diff_args(rev_a, rev_b)
    if args is None:
        return []
    out = _git(repo, "diff", "--numstat", "-M", *args, "--", *layout.roots)
    files = []
    for line in out.splitlines():
        added, deleted, path = line.split("\t", 2)
        if added != "-":
            files.append(FileChange(path, int(added), int(deleted)))
    return files


def file_diff(repo: Path, rev_a: str, rev_b: str, path: str) -> str:
    """The unified diff of one file (cut to :data:`MAX_DIFF_LINES` lines), or ''."""
    args = _diff_args(rev_a, rev_b)
    if args is None or not path:
        return ""
    lines = _git(repo, "diff", "--no-color", "-U3", *args, "--", path).splitlines()
    # drop the "diff --git / index / ---/+++" header: the viewer shows the path itself
    body = [ln for ln in lines if not ln.startswith(("diff --git", "index ", "--- ", "+++ "))]
    if len(body) > MAX_DIFF_LINES:
        body = [*body[:MAX_DIFF_LINES], f"… {len(body) - MAX_DIFF_LINES} more lines"]
    return "\n".join(body)


def _verdicts(repo: Path, rev: str, path: str) -> dict[str, dict[str, Any]]:
    """The verdicts file ``path`` as of ``rev`` ({} if it has none)."""
    try:
        worktree = rev == WORKTREE
        text = (repo / path).read_text() if worktree else _git(repo, "show", f"{rev}:{path}")
        return tomllib.loads(text)
    except OSError, RuntimeError, tomllib.TOMLDecodeError:
        return {}


def fem_hints(
    repo: Path, rev_a: str, rev_b: str, changed: list[str], verdicts: str = "fem/verdicts.toml"
) -> dict[str, str]:
    """A one-line FEM note for each changed part that has a verdict in either revision.

    "re-checked" if the verdict entry differs between the revisions; "not re-run" if the part
    changed but its entry did not (the verdict may be stale: the ``fem-status`` command tells).
    """
    verdicts_a, verdicts_b = _verdicts(repo, rev_a, verdicts), _verdicts(repo, rev_b, verdicts)
    hints = {}
    for name in changed:
        entry_a, entry_b = verdicts_a.get(name), verdicts_b.get(name)
        if entry_a is None and entry_b is None:
            continue
        if entry_a == entry_b:
            hints[name] = f"verdict {entry_b['verdict'] if entry_b else '?'} not re-run since this change"
        elif entry_a is None and entry_b is not None:
            hints[name] = f"first verdict {entry_b['verdict']}"
        elif entry_b is None and entry_a is not None:
            hints[name] = f"verdict {entry_a['verdict']} removed"
        elif entry_a is not None and entry_b is not None:
            hints[name] = f"re-checked {entry_a['verdict']} → {entry_b['verdict']}"
    return hints


def collect(
    repo: Path,
    before: Snapshot,
    after: Snapshot,
    changed_parts: list[str],
    layout: SourceLayout = SourceLayout(),  # noqa: B008
) -> dict[str, Any]:
    """Source information for the report: ``{"log", "files", "params", "parts": {name: {...}}}``."""
    parts: dict[str, dict[str, str]] = {}
    hints = fem_hints(repo, before.commit, after.commit, changed_parts, layout.verdicts_file)
    for name in changed_parts:
        part_file = after.parts.get(name) or before.parts.get(name)
        path = part_file.source if part_file and part_file.source else ""
        info = {"path": path, "diff": file_diff(repo, before.commit, after.commit, path)}
        if name in hints:
            info["fem"] = hints[name]
        parts[name] = info
    return {
        "log": commit_log(repo, before.commit, after.commit),
        "files": [
            {"path": f.path, "added": f.added, "deleted": f.deleted}
            for f in changed_files(repo, before.commit, after.commit, layout)
        ],
        "params": file_diff(repo, before.commit, after.commit, layout.params_file or ""),
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
