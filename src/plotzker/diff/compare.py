"""Compare two snapshots part by part and format the result."""

import enum
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from plotzker.diff.snapshot import Snapshot
from plotzker.diff.stlio import MeshStats, measure, read_stl, same_surface

if TYPE_CHECKING:
    from plotzker.diff.assembly import AssemblyChange

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
            b, a = self.before.size, self.after.size
            return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
        return None

    @property
    def shift(self) -> tuple[float, float, float] | None:
        """Movement of the bounding-box minimum corner (x, y, z), mm."""
        if self.before and self.after:
            b, a = self.before.bbox_min, self.after.bbox_min
            return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
        return None


def _stats(path: Path | None) -> tuple[MeshStats | None, str]:
    if path is None:
        return None, "no STL"
    try:
        return measure(read_stl(path)), ""
    except (ValueError, OSError) as exc:
        return None, str(exc)


def compare_snapshots(a: Snapshot, b: Snapshot) -> list[PartChange]:
    """Compare every part name that exists in either snapshot (sorted by name)."""
    changes = []
    for name in sorted(set(a.parts) | set(b.parts)):
        pa, pb = a.parts.get(name), b.parts.get(name)
        if pa is None:
            sb, err = _stats(pb.path if pb else None)
            changes.append(PartChange(name, Status.ADDED, after=sb, note=err))
        elif pb is None:
            sa, err = _stats(pa.path)
            changes.append(PartChange(name, Status.REMOVED, before=sa, note=err))
        else:
            changes.append(_compare_part(name, pa.path, pb.path, pa.error or pb.error))
    return changes


def _compare_part(
    name: str, path_a: Path | None, path_b: Path | None, error: str | None
) -> PartChange:
    sa, err_a = _stats(path_a)
    sb, err_b = _stats(path_b)
    if sa is None or sb is None:
        first_line = (error or err_a or err_b).strip().splitlines()[-1:] or ["unknown"]
        return PartChange(name, Status.ERROR, sa, sb, note=first_line[0])
    if sa.hash == sb.hash:
        return PartChange(name, Status.UNCHANGED, sa, sb)
    assert path_a is not None and path_b is not None
    if same_surface(read_stl(path_a), read_stl(path_b), SAME_TOLERANCE_MM):
        return PartChange(name, Status.UNCHANGED, sa, sb, note="same shape, different float noise")
    return PartChange(name, Status.CHANGED, sa, sb)


def to_json(
    a: Snapshot,
    b: Snapshot,
    changes: list[PartChange],
    assemblies: list[AssemblyChange] | None = None,
) -> str:
    """The comparison as JSON (for the later HTML viewer and for scripts)."""

    def default(o: object) -> object:
        if isinstance(o, Status):
            return o.value
        raise TypeError(type(o))

    from plotzker.diff.assembly import to_dict

    doc = {
        "a": {"label": a.label, "commit": a.commit, "error": a.error},
        "b": {"label": b.label, "commit": b.commit, "error": b.error},
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
    return json.dumps(doc, indent=1, default=default)


def _short(snap: Snapshot) -> str:
    return snap.label if snap.commit == snap.label else f"{snap.label} ({snap.commit[:8]})"


def format_report(a: Snapshot, b: Snapshot, changes: list[PartChange], show_all: bool) -> str:
    """Human-readable summary: one line per part that differs (or all with ``show_all``)."""
    lines = [f"Design diff: {_short(a)} → {_short(b)}"]
    for snap in (a, b):
        if snap.error:
            lines.append(f"  warning: {snap.label}: {snap.error.strip().splitlines()[-1]}")
    counts = {s: sum(c.status is s for c in changes) for s in Status}
    lines.append("  " + ", ".join(f"{n} {s.value}" for s, n in counts.items() if n))
    lines.append("")
    for c in changes:
        if c.status is Status.UNCHANGED and not show_all:
            continue
        lines.append(f"  {c.status.value:<9} {c.name:<28} {_detail(c)}".rstrip())
    return "\n".join(lines)


def _detail(c: PartChange) -> str:
    if c.status is Status.CHANGED:
        dv, ds, sh = c.volume_delta, c.size_delta, c.shift
        assert dv is not None and ds is not None and sh is not None
        parts = [f"volume {dv:+.1f} mm³"]
        if any(abs(x) > 1e-3 for x in ds):
            parts.append("size " + " ".join(f"{x:+.2f}" for x in ds))
        if any(abs(x) > 1e-3 for x in sh):
            parts.append("origin " + " ".join(f"{x:+.2f}" for x in sh))
        return ", ".join(parts)
    if c.status is Status.ADDED and c.after:
        return f"{c.after.volume:.1f} mm³"
    if c.status is Status.REMOVED and c.before:
        return f"{c.before.volume:.1f} mm³"
    return c.note
