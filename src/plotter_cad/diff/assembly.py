"""Compare the assemblies of two revisions: which instances were added, removed, moved or changed.

Assembly items are anonymous solids in assembly coordinates, so instances are matched by
geometry (this also works for old revisions, which have no names):

1. **Same place, same shape** (identical triangle set): unchanged.
2. **Same shape, other place** (equal volume and surface area, which rigid motion preserves):
   moved. Duplicates (screws) are paired with their nearest counterpart.
3. **Leftovers close to each other with a similar volume**: modified (the part changed shape).
4. What remains is added or removed.

Instances are labelled with the printable part of the same volume when there is one.
"""

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from plotter_cad.diff.snapshot import Snapshot
from plotter_cad.diff.stlio import Triangles, shape_hash, surface_area

#: Volumes and areas count as equal within this relative difference.
REL_TOL = 1e-4
#: A modified instance may have grown or shrunk by this factor at most, and moved this far (mm,
#: or half its diagonal if larger), to still count as "the same instance".
MAX_VOLUME_RATIO = 2.0
MIN_MODIFIED_DISTANCE_MM = 20.0
#: Shifts below this (mm) are not reported as a move.
SHIFT_EPS_MM = 1e-3


class InstanceStatus(enum.Enum):
    """What happened to one instance of an assembly."""

    UNCHANGED = "unchanged"
    MOVED = "moved"
    MODIFIED = "modified"
    ADDED = "added"
    REMOVED = "removed"


@dataclass(frozen=True)
class Item:
    """One solid of an assembly."""

    index: int  #: position in the assembly's item list
    tris: Triangles
    volume: float
    area: float
    centroid: tuple[float, float, float]  #: bounding-box center, mm
    size: tuple[float, float, float]  #: bounding-box extents, mm
    hash: str


@dataclass(frozen=True)
class InstanceChange:
    """The comparison of one instance."""

    status: InstanceStatus
    label: str
    printed: bool  #: matches a printable part (else: hardware or other)
    before: Item | None = None
    after: Item | None = None
    shift: tuple[float, float, float] | None = None  #: movement of the center, mm
    rotated: bool = False  #: moved and the bounding box changed (turned, not just shifted)


@dataclass
class AssemblyChange:
    """The comparison of one assembly."""

    name: str
    instances: list[InstanceChange] = field(default_factory=list)
    status: str = "unchanged"  #: changed, unchanged, added, removed or error
    note: str = ""

    def count(self, status: InstanceStatus) -> int:
        """Number of instances with ``status``."""
        return sum(i.status is status for i in self.instances)


def load_items(path: Path) -> list[Item]:
    """Read the items of an assembly snapshot (``.npz``), in their original order."""
    items = []
    with np.load(path) as data:
        for key in sorted(data.files, key=lambda k: int(k[1:])):
            tris = data[key].astype(np.float64)
            a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
            volume = abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)
            flat = tris.reshape(-1, 3)
            lo, hi = flat.min(axis=0), flat.max(axis=0)
            centre = (lo + hi) / 2
            items.append(
                Item(
                    index=int(key[1:]),
                    tris=tris,
                    volume=volume,
                    area=surface_area(tris),
                    centroid=(float(centre[0]), float(centre[1]), float(centre[2])),
                    size=(float(hi[0] - lo[0]), float(hi[1] - lo[1]), float(hi[2] - lo[2])),
                    hash=shape_hash(tris),
                )
            )
    return items


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= REL_TOL * max(abs(a), abs(b), 1e-9)


def _dist(a: Item, b: Item) -> float:
    return float(np.linalg.norm(np.subtract(a.centroid, b.centroid)))


def _shift(a: Item, b: Item) -> tuple[float, float, float]:
    d = np.subtract(b.centroid, a.centroid)
    return (float(d[0]), float(d[1]), float(d[2]))


def match_items(
    a_items: list[Item], b_items: list[Item]
) -> list[tuple[InstanceStatus, Item | None, Item | None]]:
    """Pair the items of two revisions of an assembly (see the module docstring)."""
    pairs: list[tuple[InstanceStatus, Item | None, Item | None]] = []
    rest_a, rest_b = list(a_items), list(b_items)

    # 1. identical shape at the same place
    by_hash: dict[str, list[Item]] = {}
    for item in rest_b:
        by_hash.setdefault(item.hash, []).append(item)
    left_a = []
    for item in rest_a:
        bucket = by_hash.get(item.hash)
        if bucket:
            other = bucket.pop(0)
            pairs.append((InstanceStatus.UNCHANGED, item, other))
        else:
            left_a.append(item)
    rest_a = left_a
    rest_b = [i for bucket in by_hash.values() for i in bucket]

    # 2. same shape somewhere else: nearest first
    candidates = sorted(
        (
            (_dist(a, b), a.index, b.index, a, b)
            for a in rest_a
            for b in rest_b
            if _close(a.volume, b.volume) and _close(a.area, b.area)
        ),
        key=lambda t: t[:3],
    )
    pairs += _take(candidates, InstanceStatus.MOVED, rest_a, rest_b)
    rest_a = [i for i in rest_a if not _used(i, pairs, 0)]
    rest_b = [i for i in rest_b if not _used(i, pairs, 1)]

    # 3. leftovers that are near each other and of similar size: the part changed
    near = []
    for a in rest_a:
        for b in rest_b:
            ratio = max(a.volume, b.volume) / max(min(a.volume, b.volume), 1e-9)
            reach = max(MIN_MODIFIED_DISTANCE_MM, 0.5 * float(np.linalg.norm(a.size)))
            if ratio <= MAX_VOLUME_RATIO and _dist(a, b) <= reach:
                near.append((_dist(a, b), a.index, b.index, a, b))
    near.sort(key=lambda t: t[:3])
    pairs += _take(near, InstanceStatus.MODIFIED, rest_a, rest_b)
    rest_a = [i for i in rest_a if not _used(i, pairs, 0)]
    rest_b = [i for i in rest_b if not _used(i, pairs, 1)]

    pairs += [(InstanceStatus.REMOVED, i, None) for i in rest_a]
    pairs += [(InstanceStatus.ADDED, None, i) for i in rest_b]
    return pairs


def _take(
    candidates: list[tuple[float, int, int, Item, Item]],
    status: InstanceStatus,
    rest_a: list[Item],
    rest_b: list[Item],
) -> list[tuple[InstanceStatus, Item | None, Item | None]]:
    """Greedily pair candidates (already sorted best first); each item is used once."""
    used_a: set[int] = set()
    used_b: set[int] = set()
    out: list[tuple[InstanceStatus, Item | None, Item | None]] = []
    for _, _, _, a, b in candidates:
        if a.index in used_a or b.index in used_b:
            continue
        used_a.add(a.index)
        used_b.add(b.index)
        out.append((status, a, b))
    return out


def _used(
    item: Item, pairs: list[tuple[InstanceStatus, Item | None, Item | None]], side: int
) -> bool:
    return any(p[1 + side] is item for p in pairs)


def part_labels(volumes: Mapping[str, float]) -> dict[float, str]:
    """Printable-part volumes → names (parts of equal volume, like left/right, are joined)."""
    labels: dict[float, str] = {}
    for name, volume in sorted(volumes.items()):
        for known in labels:
            if _close(known, volume):
                labels[known] += "/" + name
                break
        else:
            labels[volume] = name
    return labels


def _label(item: Item, labels: dict[float, str]) -> tuple[str, bool]:
    for volume, name in labels.items():
        if _close(volume, item.volume):
            return name, True
    return f"item {item.index} ({item.volume:.0f} mm³)", False


def compare_assembly(
    name: str, a: Path | None, b: Path | None, labels: dict[float, str]
) -> AssemblyChange:
    """Compare one assembly given the item files of both revisions (None: it does not exist)."""
    change = AssemblyChange(name)
    a_items = load_items(a) if a else []
    b_items = load_items(b) if b else []
    for status, ia, ib in match_items(a_items, b_items):
        ref = ib or ia
        assert ref is not None
        label, printed = _label(ref, labels)
        shift = None
        rotated = False
        if status is not InstanceStatus.UNCHANGED and ia and ib:
            shift = _shift(ia, ib)
            rotated = status is InstanceStatus.MOVED and not np.allclose(
                ia.size, ib.size, atol=1e-2
            )
        change.instances.append(InstanceChange(status, label, printed, ia, ib, shift, rotated))
    change.instances.sort(key=lambda i: (i.before or i.after).index if (i.before or i.after) else 0)  # type: ignore[union-attr]
    if a is None:
        change.status = "added"
    elif b is None:
        change.status = "removed"
    elif any(i.status is not InstanceStatus.UNCHANGED for i in change.instances):
        change.status = "changed"
    return change


def compare_assemblies(
    a: Snapshot, b: Snapshot, volumes: Mapping[str, float]
) -> list[AssemblyChange]:
    """Compare every assembly that exists in either snapshot (sorted by name).

    ``volumes`` are the printable parts' volumes (mm³), used to name instances.
    """
    labels = part_labels(volumes)
    changes = []
    for name in sorted(set(a.assemblies) | set(b.assemblies)):
        fa, fb = a.assemblies.get(name), b.assemblies.get(name)
        errors = [f.error for f in (fa, fb) if f and f.error]
        if errors or (fa and fa.path is None) or (fb and fb.path is None):
            note = errors[0].strip().splitlines()[-1] if errors else "no data"
            changes.append(AssemblyChange(name, status="error", note=note))
            continue
        changes.append(
            compare_assembly(name, fa.path if fa else None, fb.path if fb else None, labels)
        )
    return changes


def format_assemblies(changes: list[AssemblyChange], show_all: bool) -> str:
    """Text summary: one line per assembly that differs, then its changed instances."""
    lines = ["Assemblies:"]
    shown = False
    for c in changes:
        if c.status == "unchanged" and not show_all:
            continue
        shown = True
        counts = ", ".join(
            f"{c.count(s)} {s.value}"
            for s in (
                InstanceStatus.MODIFIED,
                InstanceStatus.MOVED,
                InstanceStatus.ADDED,
                InstanceStatus.REMOVED,
            )
            if c.count(s)
        )
        lines.append(f"  {c.status:<9} {c.name:<22} {counts or c.note}".rstrip())
        for i in c.instances:
            if i.status is InstanceStatus.UNCHANGED or (
                i.status is InstanceStatus.MOVED and not i.printed and not show_all
            ):
                continue
            extra = ""
            if i.shift and any(abs(x) > SHIFT_EPS_MM for x in i.shift):
                extra = (
                    "moved "
                    + " ".join(f"{x:+.2f}" for x in i.shift)
                    + (" (turned)" if i.rotated else "")
                )
            lines.append(f"      {i.status.value:<9} {i.label:<30} {extra}".rstrip())
    if not shown:
        lines.append("  no assembly changed")
    return "\n".join(lines)


def to_dict(changes: list[AssemblyChange]) -> list[dict[str, object]]:
    """The comparison as plain data (no meshes), for ``--json``."""
    out: list[dict[str, object]] = []
    for c in changes:
        out.append(
            {
                "name": c.name,
                "status": c.status,
                "note": c.note,
                "instances": [
                    {
                        "label": i.label,
                        "printed": i.printed,
                        "status": i.status.value,
                        "shift": i.shift,
                        "rotated": i.rotated,
                    }
                    for i in c.instances
                    if i.status is not InstanceStatus.UNCHANGED
                ],
            }
        )
    return out
