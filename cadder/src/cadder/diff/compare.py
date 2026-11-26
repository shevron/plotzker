"""Compare two snapshots part by part and format the result."""

import enum
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cadder.diff.snapshot import Snapshot
from cadder.diff.stlio import MeshStats, measure, read_stl, same_surface

if TYPE_CHECKING:
    from cadder.diff.assembly import AssemblyChange

#: Meshes whose triangle centroids agree within this many mm count as the same part.
SAME_TOLERANCE_MM = 1e-3


class Status(enum.Enum):
    """What happened to a part between the two revisions."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    ERROR = "error"  #: could not be built in one of the revisions


@dataclass(frozen=True)
class PartChange:
    """The comparison of one part."""

    name: str
    status: Status
    before: MeshStats | None = None
    after: MeshStats | None = None
    note: str = ""  #: build error, or other detail

    @property
    def volume_delta(self) -> float | None:
        """After minus before, mm³."""
        if self.before and self.after:
            return self.after.volume - self.before.volume
        return None

    @property
    def size_delta(self) -> tuple[float, float, float] | None:
        """Change of the bounding-box extents (x, y, z), mm."""
        if self.before and self.after:
            old, new = self.before.size, self.after.size
            return new[0] - old[0], new[1] - old[1], new[2] - old[2]
        return None

    @property
    def shift(self) -> tuple[float, float, float] | None:
        """Movement of the bounding-box minimum corner (x, y, z), mm."""
        if self.before and self.after:
            old, new = self.before.bbox_min, self.after.bbox_min
            return new[0] - old[0], new[1] - old[1], new[2] - old[2]
        return None


def _stats(path: Path | None) -> tuple[MeshStats | None, str]:
    if path is None:
        return None, "no STL"
    try:
        return measure(read_stl(path)), ""
    except (ValueError, OSError) as exc:
        return None, str(exc)


def compare_snapshots(before: Snapshot, after: Snapshot) -> list[PartChange]:
    """Compare every part name that exists in either snapshot (sorted by name)."""
    changes = []
    for name in sorted(set(before.parts) | set(after.parts)):
        part_before, part_after = before.parts.get(name), after.parts.get(name)
        if part_before is None:
            stats_after, err = _stats(part_after.path if part_after else None)
            changes.append(PartChange(name, Status.ADDED, after=stats_after, note=err))
        elif part_after is None:
            stats_before, err = _stats(part_before.path)
            changes.append(PartChange(name, Status.REMOVED, before=stats_before, note=err))
        else:
            changes.append(
                _compare_part(name, part_before.path, part_after.path, part_before.error or part_after.error)
            )
    return changes


def _compare_part(name: str, path_a: Path | None, path_b: Path | None, error: str | None) -> PartChange:
    stats_a, err_a = _stats(path_a)
    stats_b, err_b = _stats(path_b)
    if stats_a is None or stats_b is None:
        first_line = (error or err_a or err_b).strip().splitlines()[-1:] or ["unknown"]
        return PartChange(name, Status.ERROR, stats_a, stats_b, note=first_line[0])
    if stats_a.hash == stats_b.hash:
        return PartChange(name, Status.UNCHANGED, stats_a, stats_b)
    assert path_a is not None and path_b is not None
    if same_surface(read_stl(path_a), read_stl(path_b), SAME_TOLERANCE_MM):
        return PartChange(name, Status.UNCHANGED, stats_a, stats_b, note="same shape, different float noise")
    return PartChange(name, Status.CHANGED, stats_a, stats_b)


def _json_default(entry: object) -> object:
    """What ``json.dumps`` writes for a type it does not know."""
    if isinstance(entry, Status):
        return entry.value
    raise TypeError(type(entry))


def to_json(
    before: Snapshot,
    after: Snapshot,
    changes: list[PartChange],
    assemblies: list[AssemblyChange] | None = None,
) -> str:
    """The comparison as JSON (for the later HTML viewer and for scripts)."""

    from cadder.diff.assembly import to_dict

    doc = {
        "a": {"label": before.label, "commit": before.commit, "error": before.error},
        "b": {"label": after.label, "commit": after.commit, "error": after.error},
        "parts": [
            {
                **asdict(c),
                "volume_delta": c.volume_delta,
                "size_delta": c.size_delta,
                "shift": c.shift,
            }
            for c in changes
        ],
        "assemblies": to_dict(assemblies or []),
    }
    return json.dumps(doc, indent=1, default=_json_default)


def _short(snap: Snapshot) -> str:
    return snap.label if snap.commit == snap.label else f"{snap.label} ({snap.commit[:8]})"


def format_report(before: Snapshot, after: Snapshot, changes: list[PartChange], show_all: bool) -> str:
    """Human-readable summary: one line per part that differs (or all with ``show_all``)."""
    lines = [f"Design diff: {_short(before)} → {_short(after)}"]
    for snap in (before, after):
        if snap.error:
            lines.append(f"  warning: {snap.label}: {snap.error.strip().splitlines()[-1]}")
    counts = {s: sum(change.status is s for change in changes) for s in Status}
    lines.append("  " + ", ".join(f"{n} {s.value}" for s, n in counts.items() if n))
    lines.append("")
    for change in changes:
        if change.status is Status.UNCHANGED and not show_all:
            continue
        lines.append(f"  {change.status.value:<9} {change.name:<28} {_detail(change)}".rstrip())
    return "\n".join(lines)


def _detail(change: PartChange) -> str:
    if change.status is Status.CHANGED:
        volume_change, size_change, shift = change.volume_delta, change.size_delta, change.shift
        assert volume_change is not None and size_change is not None and shift is not None
        parts = [f"volume {volume_change:+.1f} mm³"]
        if any(abs(x) > 1e-3 for x in size_change):
            parts.append("size " + " ".join(f"{x:+.2f}" for x in size_change))
        if any(abs(x) > 1e-3 for x in shift):
            parts.append("origin " + " ".join(f"{x:+.2f}" for x in shift))
        return ", ".join(parts)
    if change.status is Status.ADDED and change.after:
        return f"{change.after.volume:.1f} mm³"
    if change.status is Status.REMOVED and change.before:
        return f"{change.before.volume:.1f} mm³"
    return change.note
