"""Heights from several photos: a plane sweep over the photos' rectifications.

A textured patch of a flat face (silkscreen on a PCB top, a label, a screw head) looks the
same in every photo only when each photo is rectified onto the face's true height. At a wrong
height the patch seen from another camera position is shifted, and the shift grows in
proportion to the height error (parallax). :func:`height_scan` rectifies the patch at a range
of heights in a reference photo and every other photo, finds the shift by template matching,
and fits where the shift crosses zero: that is the face's height, to a fraction of the step.
"""

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import numpy.typing as npt

from cadder.photo.image import load
from cadder.photo.target import Rectification

Gray = npt.NDArray[np.float32]


def render_plane(
    rect: Rectification,
    gray: Gray,
    box: tuple[float, float, float, float],
    z: float,
    px_per_mm: float,
) -> Gray:
    """The photo (grayscale) resampled square-on onto the plane ``z`` over ``box`` (target mm,
    x0, y0, x1, y1), at ``px_per_mm``; image rows run from y1 down to y0."""
    import cv2

    x0, y0, x1, y1 = box
    xs = x0 + np.arange(round((x1 - x0) * px_per_mm)) / px_per_mm
    ys = y1 - np.arange(round((y1 - y0) * px_per_mm)) / px_per_mm
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel(), np.full(gx.size, z)])
    uv = rect.project(pts).reshape((*gx.shape, 2)).astype(np.float32)
    return np.asarray(cv2.remap(gray, uv[..., 0], uv[..., 1], cv2.INTER_LINEAR), np.float32)


@dataclass
class ViewHeight:
    """The height found from one photo against the reference."""

    photo: str
    z: float | None  #: where the shift crosses zero (None: no usable match)
    score: float  #: template match (normalized correlation, 1 = identical) near that height
    sensitivity: float  #: shift (mm) per mm of height error: low means a weak view
    rms: float  #: scatter of the shifts about the fitted line (mm)


@dataclass
class HeightResult:
    """A face's height from all photos."""

    z: float | None  #: combined height above the paper (mm)
    spread: float  #: weighted scatter of the per-photo heights (mm)
    views: list[ViewHeight] = field(default_factory=list)
    curve: list[tuple[float, float, float, float]] = field(default_factory=list)
    #: (z, mean score, mean shift x, mean shift y) over the sweep, for plotting or reading


View = tuple[Rectification, Path]  #: a rectification and the folder of its sidecar


def height_scan(
    ref: View,
    others: list[View],
    box: tuple[float, float, float, float],
    z_range: tuple[float, float] = (0.0, 20.0),
    step: float = 0.25,
    search: float = 2.0,
    px_per_mm: float = 30.0,
) -> HeightResult:
    """The height of the flat, textured face inside ``box`` (target mm).

    For each height in ``z_range`` (every ``step``), the reference photo's patch over ``box``
    is matched in each other photo's rectification at that height, within ``search`` mm. The
    match shift is fitted with a line over the heights where the match is good; its zero is
    that photo's height. Photos are combined weighted by their sensitivity squared (a photo
    from far to the side sees more parallax and decides more).
    """
    import cv2

    def gray(view: View) -> Gray:
        img = load(view[1] / view[0].source)
        return np.asarray(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), np.float32)

    ref_gray = gray(ref)
    other_gray = [gray(o) for o in others]
    ref_rect = ref[0]
    other_rects = [o[0] for o in others]
    z_values = np.arange(z_range[0], z_range[1] + step / 2, step)
    x0, y0, x1, y1 = box
    grown = (x0 - search, y0 - search, x1 + search, y1 + search)
    pad = round(search * px_per_mm)
    shifts = np.full((len(others), len(z_values), 2), np.nan)
    scores = np.zeros((len(others), len(z_values)))
    for j, z in enumerate(z_values):
        template = render_plane(ref_rect, ref_gray, box, float(z), px_per_mm)
        if template.std() < 2:
            raise ValueError("the box has no texture to match: move it onto print or detail")
        for i, (o, other_image) in enumerate(zip(other_rects, other_gray, strict=True)):
            area = render_plane(o, other_image, grown, float(z), px_per_mm)
            res = cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED)
            _, best, _, (peak_x, peak_y) = cv2.minMaxLoc(res)
            # sub-pixel peak (parabola in x and y)
            fx = fy = 0.0
            if 0 < peak_x < res.shape[1] - 1:
                before, peak, after = res[peak_y, peak_x - 1], res[peak_y, peak_x], res[peak_y, peak_x + 1]
                fx = 0.5 * (before - after) / (before - 2 * peak + after) if (before - 2 * peak + after) else 0.0
            if 0 < peak_y < res.shape[0] - 1:
                before, peak, after = res[peak_y - 1, peak_x], res[peak_y, peak_x], res[peak_y + 1, peak_x]
                fy = 0.5 * (before - after) / (before - 2 * peak + after) if (before - 2 * peak + after) else 0.0
            dx = (peak_x + fx - pad) / px_per_mm
            dy = -(peak_y + fy - pad) / px_per_mm  # image rows run down, target y up
            shifts[i, j] = (dx, dy)
            scores[i, j] = best
    views: list[ViewHeight] = []
    for i, o in enumerate(other_rects):
        good = scores[i] >= max(0.5, 0.8 * scores[i].max())
        name = o.source
        if good.sum() < 3:
            views.append(ViewHeight(name, None, float(scores[i].max()), 0.0, math.nan))
            continue
        z_good, s_good = z_values[good], shifts[i, good]
        before = np.column_stack([np.ones(good.sum()), z_good])
        coef, *_ = np.linalg.lstsq(before, s_good, rcond=None)  # shift = c0 + c1 z, per axis
        c0, c1 = coef[0], coef[1]
        sens = float(np.hypot(*c1))
        if sens < 1e-3:
            views.append(ViewHeight(name, None, float(scores[i].max()), sens, math.nan))
            continue
        z0 = float(-(c0 @ c1) / (c1 @ c1))
        rms = float(np.sqrt(np.mean(np.sum((s_good - before @ coef) ** 2, axis=1))))
        k = int(np.argmin(np.abs(z_values - z0)))
        views.append(ViewHeight(name, z0, float(scores[i, k]), sens, rms))
    usable = [v for v in views if v.z is not None and v.score >= 0.5]
    if not usable:
        z, spread = None, math.nan
    else:
        weights = np.array([v.sensitivity**2 for v in usable])
        heights = np.array([v.z for v in usable], dtype=np.float64)
        z = float(np.sum(weights * heights) / weights.sum())
        spread = float(np.sqrt(np.sum(weights * (heights - z) ** 2) / weights.sum()))
    curve = [
        (float(z_values[j]), float(scores[:, j].mean()), *map(float, np.nanmean(shifts[:, j], axis=0)))
        for j in range(len(z_values))
    ]
    return HeightResult(z, spread, views, curve)  # type: ignore[arg-type]
