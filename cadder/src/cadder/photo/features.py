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
        data = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        angle = math.radians(self.angle_deg)
        cos_angle, sin_angle = math.cos(angle), math.sin(angle)
        x = self.origin[0] + cos_angle * data[:, 0] - sin_angle * data[:, 1]
        y = self.origin[1] + sin_angle * data[:, 0] + cos_angle * data[:, 1]
        return np.column_stack([x, y, data[:, 2]])

    def to_photo(self, points: Points) -> Points:
        """Part-frame points → photo pixels (or the points themselves in pixel mode)."""
        data = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        if self.rect is None:
            return data[:, :2]
        return self.rect.project(self.to_target(data))


def read(path: Path) -> FeatureFile:
    """Load and check a feature file (problems are listed in ``errors``)."""
    data = json.loads(path.read_text())
    base = path.parent
    feature_file = FeatureFile(path=path, features=list(data.get("features", [])))
    if "rectification" in data:
        sidecar = base / data["rectification"]
        feature_file.rect, feature_file.rect_dir = Rectification.load(sidecar), sidecar.parent
    elif "image" in data:
        feature_file.image = base / data["image"]
    else:
        feature_file.errors.append("give either 'rectification' (a .rect.json) or 'image'")
    frame = data.get("frame", {})
    origin = frame.get("origin", (0.0, 0.0))
    feature_file.origin = (float(origin[0]), float(origin[1]))
    feature_file.angle_deg = float(frame.get("angle_deg", 0.0))
    for i, f in enumerate(feature_file.features):
        name = f.get("name", f"#{i}")
        if f.get("kind") not in KINDS:
            feature_file.errors.append(f"{name}: kind must be one of {', '.join(KINDS)}")
        if f.get("kind") in ("box", "circle", "point") and "center" not in f:
            feature_file.errors.append(f"{name}: needs 'center'")
        if f.get("kind") == "box" and "size" not in f:
            feature_file.errors.append(f"{name}: needs 'size'")
        if f.get("kind") == "circle" and "d" not in f:
            feature_file.errors.append(f"{name}: needs 'd'")
        if f.get("kind") == "line" and len(f.get("points", [])) < 2:
            feature_file.errors.append(f"{name}: needs at least 2 'points'")
        if "source" not in f:
            feature_file.errors.append(f"{name}: needs 'source' (measured, datasheet, photo, assumed)")
    return feature_file


def _xyz(v: list[float]) -> list[float]:
    return [*v, 0.0][:3] if len(v) < 3 else list(v[:3])


def _outline(f: dict[str, Any]) -> list[Points]:
    """Polylines (part frame, N × 3) that draw a feature."""
    kind = f["kind"]
    if kind == "box":
        center, size = np.array(_xyz(f["center"])), np.array(_xyz(f["size"]))
        lower, upper = center - size / 2, center + size / 2
        corners = np.array(
            [[x, y, z] for z in (lower[2], upper[2]) for x, y in
             ((lower[0], lower[1]), (upper[0], lower[1]), (upper[0], upper[1]), (lower[0], upper[1]))]
        )  # fmt: skip
        lines = [corners[[0, 1, 2, 3, 0]], corners[[4, 5, 6, 7, 4]]]
        lines += [corners[[i, i + 4]] for i in range(4)]
        return lines
    if kind == "circle":
        center = np.array(_xyz(f["center"]))
        angles = np.linspace(0, 2 * math.pi, 73)
        radius = f["d"] / 2
        return [
            np.column_stack(
                [center[0] + radius * np.cos(angles), center[1] + radius * np.sin(angles), np.full(73, center[2])]
            )
        ]
    if kind == "line":
        return [np.array([_xyz(p) for p in f["points"]], dtype=np.float64)]
    return [np.array([_xyz(f["center"])], dtype=np.float64)]


def overlay(
    feature_file: FeatureFile,
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
        feature_file.rect, feature_file.rect_dir = Rectification.load(rect), rect.parent

    def same(line_points: Points) -> Points:
        return line_points

    to_img: Callable[[Points], Points] = same
    if feature_file.rect is None:
        assert feature_file.image is not None
        image = load(feature_file.image)
    elif on == "rectified":
        assert feature_file.rect_dir is not None
        image = load(feature_file.rect_dir / feature_file.rect.image)
        to_img = feature_file.rect.photo_to_rect
    else:
        assert feature_file.rect_dir is not None
        image = load(feature_file.rect_dir / feature_file.rect.source)
    drawn: list[tuple[str, tuple[int, int, int], list[Points]]] = []
    for f in feature_file.features:
        if f.get("kind") not in KINDS:
            continue
        color = COLORS.get(str(f.get("source", "")).split()[0], (255, 255, 255))
        drawn.append((str(f.get("name", "")), color, [to_img(feature_file.to_photo(line)) for line in _outline(f)]))
    x0 = y0 = 0
    if crop is not None and drawn:
        allp = np.vstack([line_points for _, _, lines in drawn for line_points in lines])
        px_per_mm = 1.0
        if feature_file.rect is not None:  # the image's scale near the features
            target_x = np.mean(feature_file.to_target(np.array([[0.0, 0, 0], [1, 0, 0]])), axis=0)
            pair = to_img(feature_file.rect.project(np.array([target_x, target_x + np.array([1.0, 0.0, 0.0])])))
            px_per_mm = float(np.hypot(*(pair[1] - pair[0])))
        margin_px = crop * px_per_mm
        image_height, image_width = image.shape[:2]
        x0, y0 = max(0, int(allp[:, 0].min() - margin_px)), max(0, int(allp[:, 1].min() - margin_px))
        x1, y1 = (
            min(image_width, int(allp[:, 0].max() + margin_px)),
            min(image_height, int(allp[:, 1].max() + margin_px)),
        )
        image = np.ascontiguousarray(image[y0:y1, x0:x1])
    scale = max(image.shape[:2]) / 1500
    thick, font_scale = max(1, round(1.5 * scale)), 0.7 * scale
    legend = []
    for number, (name, color, lines) in enumerate(drawn, 1):
        first = None
        for line in lines:
            pts = np.round(line - [x0, y0]).astype(np.int32).reshape(-1, 2)
            if len(pts) == 1:
                anchor = (int(pts[0, 0]), int(pts[0, 1]))
                cv2.drawMarker(image, anchor, color, cv2.MARKER_CROSS, round(14 * scale), thick)
            else:
                cv2.polylines(image, [pts], False, color, thick, cv2.LINE_AA)
            first = first or (int(pts[0, 0]), int(pts[0, 1]))
        text = {"names": name, "numbers": str(number)}.get(labels)
        if text and first is not None:
            cv2.putText(
                image, text, (first[0] + 4, first[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thick, cv2.LINE_AA,
            )  # fmt: skip
        legend.append(f"{number} {name}")
    return image, legend


def _fmt(v: object) -> str:
    if isinstance(v, (list, tuple)):
        return ", ".join(_fmt(x) for x in v)
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)


def table(feature_file: FeatureFile) -> str:
    """The features as a Markdown table (the report's "Features" section)."""
    rows = [
        "| Feature | Kind | Position (x, y, z) | Size | Source | ± | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in feature_file.features:
        kind = f.get("kind", "")
        if kind == "line":
            pos = " → ".join(f"({_fmt(p)})" for p in f.get("points", []))
        else:
            pos = f"({_fmt(f.get('center', ''))})"
        size = _fmt(f.get("size", "")) if kind == "box" else (f"Ø{_fmt(f['d'])}" if "d" in f else "")
        rows.append(
            f"| {f.get('name', '')} | {kind} | {pos} | {size} | {f.get('source', '')} "
            f"| {_fmt(f.get('band', ''))} | {f.get('notes', '')} |"
        )
    return "\n".join(rows)
