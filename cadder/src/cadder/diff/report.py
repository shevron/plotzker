"""Write the self-contained HTML report of a design diff.

One ``index.html`` with the meshes embedded (base64 float32 triangles), so it opens from disk,
works offline and can be sent as one file. The viewer (``viewer/viewer.html``) is plain WebGL2
with no libraries: three.js would have to be downloaded and vendored, and the viewer's needs
(translucent overlays, a swipe split, orbit camera) are small.
"""

import base64
import hashlib
import json
import zlib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cadder.diff.assembly import AssemblyChange, InstanceChange, InstanceStatus
from cadder.diff.boolean import solid_diff
from cadder.diff.compare import PartChange, Status
from cadder.diff.snapshot import Snapshot
from cadder.diff.stlio import Triangles, read_stl

VIEWER = Path(__file__).parent / "viewer" / "viewer.html"
_PLACEHOLDER = "/*__DIFF_DATA__*/null"


class MeshTable:
    """The meshes of a report, each stored once (by content) as deflated base64 float32.

    An assembly instance that is identical in several assemblies, or in an assembly and as a
    part, costs one entry. The viewer decodes them on demand (``DecompressionStream``).
    """

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def add(self, tris: Triangles | None) -> str | None:
        """Store ``tris`` (9 float32 per triangle); returns its id, or None for no mesh."""
        if tris is None:
            return None
        raw = tris.astype("<f4").reshape(-1).tobytes()
        key = hashlib.sha1(raw).hexdigest()[:12]
        if key not in self.data:
            self.data[key] = base64.b64encode(zlib.compress(raw, 6)).decode("ascii")
        return key


def _tris(snap: Snapshot, name: str) -> Triangles | None:
    part = snap.parts.get(name)
    return None if part is None or part.path is None else read_stl(part.path)


def _instance_data(i: InstanceChange, table: MeshTable) -> dict[str, Any]:
    """One assembly instance for the viewer: meshes as needed to draw its status."""
    tris_before = i.before.tris if i.before else None
    tris_after = i.after.tris if i.after else None
    ref = i.after or i.before
    entry: dict[str, Any] = {
        "label": i.label,
        "printed": i.printed,
        "status": i.status.value,
        "shift": i.shift,
        "rotated": i.rotated,
        "volume": ref.volume if ref else 0,
        "meshA": None,
        "meshB": None,
        "meshAdded": None,
        "meshRemoved": None,
        "addedVolume": None,
        "removedVolume": None,
    }
    if i.status is InstanceStatus.UNCHANGED:
        entry["meshB"] = table.add(tris_after)  # context: only the new shape
        return entry
    entry["meshA"], entry["meshB"] = table.add(tris_before), table.add(tris_after)
    if i.status is InstanceStatus.MODIFIED and tris_before is not None and tris_after is not None:
        try:
            diff = solid_diff(tris_before, tris_after)
        except ValueError:
            return entry
        entry["meshAdded"], entry["meshRemoved"] = table.add(diff.added), table.add(diff.removed)
        entry["addedVolume"], entry["removedVolume"] = diff.added_volume, diff.removed_volume
    return entry


def _assembly_data(change: AssemblyChange, table: MeshTable) -> dict[str, Any]:
    counts = {s.value: change.count(s) for s in InstanceStatus if s is not InstanceStatus.UNCHANGED}
    entry: dict[str, Any] = {
        "name": change.name,
        "status": change.status,
        "note": change.note,
        "counts": counts,
        "instances": [],
    }
    if change.status in ("changed", "added", "removed"):
        entry["instances"] = [_instance_data(i, table) for i in change.instances]
    return entry


def report_data(
    before: Snapshot,
    after: Snapshot,
    changes: list[PartChange],
    assemblies: list[AssemblyChange] | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything the viewer needs, JSON-serializable."""
    table = MeshTable()
    parts = []
    for change in changes:
        entry: dict[str, Any] = {
            "name": change.name,
            "status": change.status.value,
            "note": change.note,
            "before": asdict(change.before) if change.before else None,
            "after": asdict(change.after) if change.after else None,
            "volume_delta": change.volume_delta,
            "size_delta": change.size_delta,
            "shift": change.shift,
            "meshA": None,
            "meshB": None,
            "meshAdded": None,
            "meshRemoved": None,
            "addedVolume": None,
            "removedVolume": None,
        }
        if change.status is not Status.UNCHANGED:  # unchanged parts need no mesh
            tris_before = _tris(before, change.name) if change.before else None
            tris_after = _tris(after, change.name) if change.after else None
            entry["meshA"], entry["meshB"] = table.add(tris_before), table.add(tris_after)
            if tris_before is not None and tris_after is not None:
                try:
                    diff = solid_diff(tris_before, tris_after)
                except ValueError as exc:
                    entry["note"] = f"material diff unavailable: {exc}"
                else:
                    entry["meshAdded"] = table.add(diff.added)
                    entry["meshRemoved"] = table.add(diff.removed)
                    entry["addedVolume"] = diff.added_volume
                    entry["removedVolume"] = diff.removed_volume
        parts.append(entry)
    return {
        "a": {"label": before.label, "commit": before.commit},
        "b": {"label": after.label, "commit": after.commit},
        "parts": parts,
        "assemblies": [_assembly_data(change, table) for change in assemblies or []],
        "meshes": table.data,
        "source": source or {"log": [], "files": [], "params": "", "parts": {}},
    }


def _safe(label: str) -> str:
    """A revision label as a folder name."""
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in label)


def write_report(
    before: Snapshot,
    after: Snapshot,
    changes: list[PartChange],
    out_dir: Path,
    assemblies: list[AssemblyChange] | None = None,
    source: dict[str, Any] | None = None,
) -> Path:
    """Write ``<out_dir>/<a>..<b>/index.html``; returns its path."""
    folder = out_dir / f"{_safe(before.label)}..{_safe(after.label)}"
    folder.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report_data(before, after, changes, assemblies, source), separators=(",", ":")).replace(
        "</", "<\\/"
    )
    html = VIEWER.read_text().replace(_PLACEHOLDER, data)
    path = folder / "index.html"
    path.write_text(html)
    return path
