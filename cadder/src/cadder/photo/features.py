"""The feature file: what was measured, in the part's own frame, with sources and bands.

One JSON file per object is the single record of a measurement: :func:`overlay` draws it onto
the photo (to check it) and :func:`table` prints it (for the report), so the two cannot
disagree. Format::

    {
      "rectification": "top.rect.json",   // sidecar; coordinates are mm in the part frame
      "frame": {"origin": [x, y], "angle_deg": a},  // the part frame in target mm (optional)
      "features": [
        {"name": "PCB", "kind": "box", "center": [0, 0, 0.75], "size": [20.3, 20, 1.5],
         "source": "photo", "band": 0.2, "notes": "..."},
        {"name": "hole 1", "kind": "circle", "center": [-7, 7.5, 1.5], "d": 3.2, ...},
        {"name": "lever", "kind": "line", "points": [[...], [...]], ...},
        {"name": "lever tip", "kind": "point", "center": [...], ...}
      ]
    }

Without ``rectification``, give ``"image": "photo.jpg"`` instead: coordinates are then that
image's pixels (x right, y down, z ignored).

Part frame: x, y in the target's plane, rotated by ``angle_deg`` about z and shifted to
``origin``; z is height above the paper. A ``box`` is axis-aligned in the part frame.
"""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from cadder.photo.image import BGR, load
from cadder.photo.target import Rectification

Points = npt.NDArray[np.float64]

KINDS = ("box", "circle", "line", "point")
#: Overlay colors (BGR) by source tag.
COLORS = {
    "measured": (60, 200, 60),
    "datasheet": (255, 160, 0),
    "photo": (0, 200, 255),
    "assumed": (200, 80, 255),
}


@dataclass
class FeatureFile:
    """A loaded feature file."""

    path: Path
    features: list[dict[str, Any]]
    rect: Rectification | None = None
    rect_dir: Path | None = None
    image: Path | None = None
    origin: tuple[float, float] = (0.0, 0.0)
    angle_deg: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_target(self, points: Points) -> Points:
        """Part-frame points (N × 3) → target frame."""
        p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        a = math.radians(self.angle_deg)
        c, s = math.cos(a), math.sin(a)
        x = self.origin[0] + c * p[:, 0] - s * p[:, 1]
        y = self.origin[1] + s * p[:, 0] + c * p[:, 1]
        return np.column_stack([x, y, p[:, 2]])

    def to_photo(self, points: Points) -> Points:
        """Part-frame points → photo pixels (or the points themselves in pixel mode)."""
        p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        if self.rect is None:
            return p[:, :2]
        return self.rect.project(self.to_target(p))


def read(path: Path) -> FeatureFile:
    """Load and check a feature file (problems are listed in ``errors``)."""
    data = json.loads(path.read_text())
    base = path.parent
    ff = FeatureFile(path=path, features=list(data.get("features", [])))
    if "rectification" in data:
        sidecar = base / data["rectification"]
        ff.rect, ff.rect_dir = Rectification.load(sidecar), sidecar.parent
    elif "image" in data:
        ff.image = base / data["image"]
    else:
        ff.errors.append("give either 'rectification' (a .rect.json) or 'image'")
    frame = data.get("frame", {})
    origin = frame.get("origin", (0.0, 0.0))
    ff.origin = (float(origin[0]), float(origin[1]))
    ff.angle_deg = float(frame.get("angle_deg", 0.0))
    for i, f in enumerate(ff.features):
        name = f.get("name", f"#{i}")
        if f.get("kind") not in KINDS:
            ff.errors.append(f"{name}: kind must be one of {', '.join(KINDS)}")
        if f.get("kind") in ("box", "circle", "point") and "center" not in f:
            ff.errors.append(f"{name}: needs 'center'")
        if f.get("kind") == "box" and "size" not in f:
            ff.errors.append(f"{name}: needs 'size'")
        if f.get("kind") == "circle" and "d" not in f:
            ff.errors.append(f"{name}: needs 'd'")
        if f.get("kind") == "line" and len(f.get("points", [])) < 2:
            ff.errors.append(f"{name}: needs at least 2 'points'")
        if "source" not in f:
            ff.errors.append(f"{name}: needs 'source' (measured, datasheet, photo, assumed)")
    return ff


def _xyz(v: list[float]) -> list[float]:
    return [*v, 0.0][:3] if len(v) < 3 else list(v[:3])


def _outline(f: dict[str, Any]) -> list[Points]:
    """Polylines (part frame, N × 3) that draw a feature."""
    kind = f["kind"]
    if kind == "box":
        c, s = np.array(_xyz(f["center"])), np.array(_xyz(f["size"]))
        lo, hi = c - s / 2, c + s / 2
        corners = np.array(
            [[x, y, z] for z in (lo[2], hi[2]) for x, y in
             ((lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1]))]
        )  # fmt: skip
        lines = [corners[[0, 1, 2, 3, 0]], corners[[4, 5, 6, 7, 4]]]
        lines += [corners[[i, i + 4]] for i in range(4)]
        return lines
    if kind == "circle":
        c = np.array(_xyz(f["center"]))
        a = np.linspace(0, 2 * math.pi, 73)
        r = f["d"] / 2
        return [np.column_stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a), np.full(73, c[2])])]
    if kind == "line":
        return [np.array([_xyz(p) for p in f["points"]], dtype=np.float64)]
    return [np.array([_xyz(f["center"])], dtype=np.float64)]


def overlay(
    ff: FeatureFile,
    on: str = "photo",
    labels: str = "names",
    rect: Path | None = None,
    crop: float | None = None,
) -> tuple[BGR, list[str]]:
    """Draw the features on the photo (``on="photo"``) or its rectified image (``"rectified"``).

    Colors by source: green measured, blue datasheet, yellow photo, magenta assumed.
    ``rect`` draws on another photo of the same set (its ``.rect.json``) instead of the one the
    file names; ``crop`` (mm) cuts the image down to the features plus that margin;
    ``labels`` is ``names``, ``numbers`` (with a legend, for small parts) or ``none``. Returns
    the image and the legend lines.
    """
    import cv2

    if rect is not None:
        ff.rect, ff.rect_dir = Rectification.load(rect), rect.parent

    def same(p: Points) -> Points:
        return p

    to_img: Callable[[Points], Points] = same
    if ff.rect is None:
        assert ff.image is not None
        image = load(ff.image)
    elif on == "rectified":
        assert ff.rect_dir is not None
        image = load(ff.rect_dir / ff.rect.image)
        to_img = ff.rect.photo_to_rect
    else:
        assert ff.rect_dir is not None
        image = load(ff.rect_dir / ff.rect.source)
    drawn: list[tuple[str, tuple[int, int, int], list[Points]]] = []
    for f in ff.features:
        if f.get("kind") not in KINDS:
            continue
        color = COLORS.get(str(f.get("source", "")).split()[0], (255, 255, 255))
        drawn.append(
            (str(f.get("name", "")), color, [to_img(ff.to_photo(line)) for line in _outline(f)])
        )
    x0 = y0 = 0
    if crop is not None and drawn:
        allp = np.vstack([p for _, _, lines in drawn for p in lines])
        px_per_mm = 1.0
        if ff.rect is not None:  # the image's scale near the features
            c = np.mean(ff.to_target(np.array([[0.0, 0, 0], [1, 0, 0]])), axis=0)
            pair = to_img(ff.rect.project(np.array([c, c + np.array([1.0, 0.0, 0.0])])))
            px_per_mm = float(np.hypot(*(pair[1] - pair[0])))
        m = crop * px_per_mm
        h, w = image.shape[:2]
        x0, y0 = max(0, int(allp[:, 0].min() - m)), max(0, int(allp[:, 1].min() - m))
        x1, y1 = min(w, int(allp[:, 0].max() + m)), min(h, int(allp[:, 1].max() + m))
        image = np.ascontiguousarray(image[y0:y1, x0:x1])
    scale = max(image.shape[:2]) / 1500
    thick, font_scale = max(1, round(1.5 * scale)), 0.7 * scale
    legend = []
    for n, (name, color, lines) in enumerate(drawn, 1):
        first = None
        for line in lines:
            pts = np.round(line - [x0, y0]).astype(np.int32).reshape(-1, 2)
            if len(pts) == 1:
                at = (int(pts[0, 0]), int(pts[0, 1]))
                cv2.drawMarker(image, at, color, cv2.MARKER_CROSS, round(14 * scale), thick)
            else:
                cv2.polylines(image, [pts], False, color, thick, cv2.LINE_AA)
            first = first or (int(pts[0, 0]), int(pts[0, 1]))
        text = {"names": name, "numbers": str(n)}.get(labels)
        if text and first is not None:
            cv2.putText(
                image, text, (first[0] + 4, first[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thick, cv2.LINE_AA,
            )  # fmt: skip
        legend.append(f"{n} {name}")
    return image, legend


def _fmt(v: object) -> str:
    if isinstance(v, (list, tuple)):
        return ", ".join(_fmt(x) for x in v)
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)


def table(ff: FeatureFile) -> str:
    """The features as a Markdown table (the report's "Features" section)."""
    rows = [
        "| Feature | Kind | Position (x, y, z) | Size | Source | ± | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in ff.features:
        kind = f.get("kind", "")
        if kind == "line":
            pos = " → ".join(f"({_fmt(p)})" for p in f.get("points", []))
        else:
            pos = f"({_fmt(f.get('center', ''))})"
        size = (
            _fmt(f.get("size", "")) if kind == "box" else (f"Ø{_fmt(f['d'])}" if "d" in f else "")
        )
        rows.append(
            f"| {f.get('name', '')} | {kind} | {pos} | {size} | {f.get('source', '')} "
            f"| {_fmt(f.get('band', ''))} | {f.get('notes', '')} |"
        )
    return "\n".join(rows)
