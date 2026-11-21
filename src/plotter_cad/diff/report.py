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

from plotter_cad.diff.assembly import AssemblyChange, InstanceChange, InstanceStatus
from plotter_cad.diff.boolean import solid_diff
from plotter_cad.diff.compare import PartChange, Status
from plotter_cad.diff.snapshot import Snapshot
from plotter_cad.diff.stlio import Triangles, read_stl

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
    ta = i.before.tris if i.before else None
    tb = i.after.tris if i.after else None
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
        entry["meshB"] = table.add(tb)  # context: only the new shape
        return entry
    entry["meshA"], entry["meshB"] = table.add(ta), table.add(tb)
    if i.status is InstanceStatus.MODIFIED and ta is not None and tb is not None:
        try:
            diff = solid_diff(ta, tb)
        except ValueError:
            return entry
        entry["meshAdded"], entry["meshRemoved"] = table.add(diff.added), table.add(diff.removed)
        entry["addedVolume"], entry["removedVolume"] = diff.added_volume, diff.removed_volume
    return entry


def _assembly_data(c: AssemblyChange, table: MeshTable) -> dict[str, Any]:
    counts = {s.value: c.count(s) for s in InstanceStatus if s is not InstanceStatus.UNCHANGED}
    entry: dict[str, Any] = {
        "name": c.name,
        "status": c.status,
        "note": c.note,
        "counts": counts,
        "instances": [],
    }
    if c.status in ("changed", "added", "removed"):
        entry["instances"] = [_instance_data(i, table) for i in c.instances]
    return entry


def report_data(
    a: Snapshot,
    b: Snapshot,
    changes: list[PartChange],
    assemblies: list[AssemblyChange] | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything the viewer needs, JSON-serializable."""
    table = MeshTable()
    parts = []
    for c in changes:
        entry: dict[str, Any] = {
            "name": c.name,
            "status": c.status.value,
            "note": c.note,
            "before": asdict(c.before) if c.before else None,
            "after": asdict(c.after) if c.after else None,
            "volume_delta": c.volume_delta,
            "size_delta": c.size_delta,
            "shift": c.shift,
            "meshA": None,
            "meshB": None,
            "meshAdded": None,
            "meshRemoved": None,
            "addedVolume": None,
            "removedVolume": None,
        }
        if c.status is not Status.UNCHANGED:  # unchanged parts need no mesh
            ta = _tris(a, c.name) if c.before else None
            tb = _tris(b, c.name) if c.after else None
            entry["meshA"], entry["meshB"] = table.add(ta), table.add(tb)
            if ta is not None and tb is not None:
                try:
                    diff = solid_diff(ta, tb)
                except ValueError as exc:
                    entry["note"] = f"material diff unavailable: {exc}"
                else:
                    entry["meshAdded"] = table.add(diff.added)
                    entry["meshRemoved"] = table.add(diff.removed)
                    entry["addedVolume"] = diff.added_volume
                    entry["removedVolume"] = diff.removed_volume
        parts.append(entry)
    return {
        "a": {"label": a.label, "commit": a.commit},
        "b": {"label": b.label, "commit": b.commit},
        "parts": parts,
        "assemblies": [_assembly_data(c, table) for c in assemblies or []],
        "meshes": table.data,
        "source": source or {"log": [], "files": [], "params": "", "parts": {}},
    }


def _safe(label: str) -> str:
    """A revision label as a folder name."""
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in label)


def write_report(
    a: Snapshot,
    b: Snapshot,
    changes: list[PartChange],
    out_dir: Path,
    assemblies: list[AssemblyChange] | None = None,
    source: dict[str, Any] | None = None,
) -> Path:
    """Write ``<out_dir>/<a>..<b>/index.html``; returns its path."""
    folder = out_dir / f"{_safe(a.label)}..{_safe(b.label)}"
    folder.mkdir(parents=True, exist_ok=True)
    data = json.dumps(
        report_data(a, b, changes, assemblies, source), separators=(",", ":")
    ).replace("</", "<\\/")
    html = VIEWER.read_text().replace(_PLACEHOLDER, data)
    path = folder / "index.html"
    path.write_text(html)
    return path
