"""Measuring on an image: enlarged crops with a coordinate grid, edges along a line, holes.

Coordinates are pixels of the image, or target millimeters when the image is a rectified one
(``Scale`` built from its sidecar). Every function returns plain numbers so an agent can use
them directly; the crop is for looking, the others are for numbers.
"""

import math
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import numpy.typing as npt

from cadder.photo.image import BGR
from cadder.photo.target import Rectification

Points = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Scale:
    """Image pixels ↔ the coordinates the user works in (pixels, or mm of a rectified image)."""

    rect: Rectification | None = None

    @property
    def unit(self) -> str:
        """``"mm"`` for a rectified image, else ``"px"``."""
        return "mm" if self.rect else "px"

    def to_px(self, xy: Points) -> Points:
        """User coordinates → image pixels."""
        p = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
        return self.rect.mm_to_rect(p) if self.rect else p

    def from_px(self, uv: Points) -> Points:
        """Image pixels → user coordinates."""
        p = np.asarray(uv, dtype=np.float64).reshape(-1, 2)
        return self.rect.rect_to_mm(p) if self.rect else p

    @property
    def px_per_unit(self) -> float:
        """Image pixels per user unit."""
        return self.rect.px_per_mm if self.rect else 1.0


def _box_px(scale: Scale, box: tuple[float, float, float, float], shape: tuple[int, ...]) -> tuple[int, int, int, int]:
    """A box in user coordinates → integer pixel bounds clipped to the image."""
    (u0, v0), (u1, v1) = scale.to_px(np.array([box[:2], box[2:]]))
    lo_u, hi_u = sorted((u0, u1))
    lo_v, hi_v = sorted((v0, v1))
    h, w = shape[:2]
    return (
        max(0, math.floor(lo_u)),
        max(0, math.floor(lo_v)),
        min(w, math.ceil(hi_u)),
        min(h, math.ceil(hi_v)),
    )


def nice_step(span: float) -> float:
    """A round grid step giving about 10 lines over ``span``."""
    raw = span / 10
    mag = 10 ** math.floor(math.log10(raw))
    return float(next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw))


def crop(
    image: BGR,
    scale: Scale,
    box: tuple[float, float, float, float],
    grid: float | None = None,
    max_side: int = 1400,
) -> BGR:
    """The region ``box`` (x0, y0, x1, y1 in user units), enlarged to ``max_side``, with a
    labeled grid every ``grid`` units (default: about 10 lines); every 5th line is red."""
    import cv2

    u0, v0, u1, v1 = _box_px(scale, box, image.shape)
    if u1 <= u0 or v1 <= v0:
        raise ValueError("the crop box is outside the image")
    part = image[v0:v1, u0:u1]
    k = max_side / max(part.shape[:2])
    out = cv2.resize(part, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC if k > 1 else cv2.INTER_AREA)
    (x0, y0), (x1, y1) = scale.from_px(np.array([[u0, v0], [u1, v1]], dtype=np.float64))
    xs, ys = sorted((x0, x1)), sorted((y0, y1))
    step = grid or nice_step(max(xs[1] - xs[0], ys[1] - ys[0]))
    for axis, (lo, hi) in enumerate((xs, ys)):
        n0 = math.ceil(lo / step - 1e-9)
        for n in range(n0, math.floor(hi / step + 1e-9) + 1):
            value = n * step
            point = np.array([[value, ys[0]]] if axis == 0 else [[xs[0], value]])
            u, v = scale.to_px(point)[0]
            color = (0, 0, 255) if n % 5 == 0 else (0, 220, 255)
            label = f"{value:g}"
            if axis == 0:
                x = round((u - u0) * k)
                cv2.line(out, (x, 0), (x, out.shape[0]), color, 1)
                cv2.putText(out, label, (x + 3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
            else:
                y = round((v - v0) * k)
                cv2.line(out, (0, y), (out.shape[1], y), color, 1)
                cv2.putText(out, label, (3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    cv2.putText(out, scale.unit, (out.shape[1] - 40, out.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
    return np.asarray(out, dtype=np.uint8)


@dataclass(frozen=True)
class Edge:
    """An intensity step along a measuring line."""

    position: float  #: distance from the line's start (user units)
    x: float
    y: float
    strength: float  #: gradient magnitude (gray levels per pixel)
    rising: bool  #: dark → light going along the line


def edges(
    image: BGR,
    scale: Scale,
    start: tuple[float, float],
    end: tuple[float, float],
    band: float = 5,
    count: int = 6,
    min_strength: float = 8,
    first: bool = False,
    polarity: str | None = None,
) -> list[Edge]:
    """Edges along the line ``start`` → ``end`` (user units), to sub-pixel.

    The profile is averaged over ``band`` pixels across the line (to beat noise and texture);
    edge positions come from the gradient's peaks, refined with a parabola. By default the
    ``count`` strongest are returned; with ``first``, the first ``count`` from ``start`` (to
    find an object's outer edge before the print or texture inside it). ``polarity``
    (``"rising"`` dark→light or ``"falling"`` light→dark) keeps only one kind.
    """
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    (a, b) = scale.to_px(np.array([start, end]))
    length = float(np.hypot(*(b - a)))
    if length < 3:
        raise ValueError("the measuring line is too short")
    n = max(3, round(length * 2))  # half-pixel samples
    t = np.linspace(0, 1, n)
    along = (b - a) / length
    normal = np.array([-along[1], along[0]])
    offsets = np.linspace(-band / 2, band / 2, max(1, round(band)))
    pts = a[None, None, :] + (t[:, None, None] * (b - a)) + offsets[None, :, None] * normal
    map_x = pts[..., 0].astype(np.float32)
    map_y = pts[..., 1].astype(np.float32)
    samples = cv2.remap(gray, map_x, map_y, cv2.INTER_LINEAR)
    profile = cv2.GaussianBlur(samples.mean(axis=1).reshape(-1, 1), (1, 5), 1.0).ravel()
    step = length / (n - 1)
    grad = np.gradient(profile) / step
    mag = np.abs(grad)
    peaks = [i for i in range(1, n - 1) if mag[i] >= mag[i - 1] and mag[i] > mag[i + 1] and mag[i] >= min_strength]
    if polarity in ("rising", "falling"):
        peaks = [i for i in peaks if (grad[i] > 0) == (polarity == "rising")]
    elif polarity is not None:
        raise ValueError("polarity must be 'rising' or 'falling'")
    peaks.sort(key=(lambda i: i) if first else (lambda i: -mag[i]))
    found = []
    for i in peaks[:count]:
        denom = mag[i - 1] - 2 * mag[i] + mag[i + 1]
        frac = 0.5 * (mag[i - 1] - mag[i + 1]) / denom if denom else 0.0
        s_px = (i + frac) * step
        xy = scale.from_px((a + along * s_px)[None, :])[0]
        found.append(
            Edge(
                position=s_px / scale.px_per_unit,
                x=float(xy[0]),
                y=float(xy[1]),
                strength=float(mag[i]),
                rising=bool(grad[i] > 0),
            )
        )
    return sorted(found, key=lambda e: e.position)


@dataclass(frozen=True)
class Hole:
    """A round feature found in a region: center, diameters and the fit's quality.

    It is fitted as an ellipse: a circle seen at an angle (an unrectified photo) is one.
    """

    x: float
    y: float
    diameter: float  #: major axis (the true diameter when seen at an angle)
    rms: float  #: RMS distance of the edge points from the fitted ellipse (user units)
    points: int  #: rays (of 120) that found the edge
    minor: float = 0.0  #: minor axis: equal to the diameter on a square-on (rectified) image
    angle_deg: float = 0.0  #: direction of the major axis
    hole: int = 0  #: which hole (1 = best supported); its concentric edges share the number
    ring: int = 0  #: which edge of that hole, from the inside out (1 = innermost)


def fit_circle(points: Points) -> tuple[float, float, float, float]:
    """Least-squares circle through ``points`` (N × 2): center x, y, radius, RMS residual."""
    p = np.asarray(points, dtype=np.float64)
    a = np.column_stack([2 * p[:, 0], 2 * p[:, 1], np.ones(len(p))])
    rhs = (p**2).sum(axis=1)
    (cx, cy, c), *_ = np.linalg.lstsq(a, rhs, rcond=None)
    r = math.sqrt(c + cx * cx + cy * cy)
    rms = float(np.sqrt(np.mean((np.hypot(p[:, 0] - cx, p[:, 1] - cy) - r) ** 2)))
    return float(cx), float(cy), r, rms


RAYS = 120  #: rays cast around a hole candidate


def _ray_peaks(
    mag: npt.NDArray[np.float32], cx: float, cy: float, radius_lo: float, radius_hi: float
) -> dict[int, list[tuple[float, float, float]]]:
    """Gradient peaks on ``RAYS`` rays from (cx, cy) between radii ``radius_lo`` and ``radius_hi``:
    ray index → [(x, y, radius)], sub-pixel, every local maximum above a quarter of the ray's
    strongest."""
    import cv2

    n = max(32, round((radius_hi - radius_lo) * 2))
    radii = np.linspace(radius_lo, radius_hi, n)
    step = radii[1] - radii[0]
    out: dict[int, list[tuple[float, float, float]]] = {}
    for ray in range(RAYS):
        ang = 2 * math.pi * ray / RAYS
        c, s = math.cos(ang), math.sin(ang)
        xs, ys = cx + c * radii, cy + s * radii
        ok = (xs >= 1) & (ys >= 1) & (xs < mag.shape[1] - 2) & (ys < mag.shape[0] - 2)
        if ok.sum() < 5:
            continue
        rr = radii[ok]
        vals = cv2.remap(
            mag, xs[ok].astype(np.float32).reshape(1, -1),
            ys[ok].astype(np.float32).reshape(1, -1), cv2.INTER_LINEAR,
        ).ravel()  # fmt: skip
        floor = 0.25 * float(vals.max())
        for j in range(1, len(vals) - 1):
            if vals[j] >= vals[j - 1] and vals[j] > vals[j + 1] and vals[j] >= floor:
                denom = vals[j - 1] - 2 * vals[j] + vals[j + 1]
                frac = 0.5 * (vals[j - 1] - vals[j + 1]) / denom if denom else 0.0
                r = float(rr[j] + frac * step)
                out.setdefault(ray, []).append((cx + c * r, cy + s * r, r))
    return out


def _ellipse_radius(e: tuple[float, float, float, float, float], ang: float) -> float:
    """Distance from an ellipse's center to its edge in direction ``ang`` (radians).

    ``e`` is (cx, cy, a, b, phi): center, semi-axes, major axis direction.
    """
    _, _, a, b, phi = e
    t = ang - phi
    return a * b / math.hypot(b * math.cos(t), a * math.sin(t))


def _track(mag: npt.NDArray[np.float32], cx: float, cy: float, r: float) -> Hole | None:
    """Follow one circular edge near radius ``r`` around (cx, cy) and fit an ellipse to it.

    On each ray the gradient peak nearest the current estimate is taken, then the ellipse is
    refitted; a few rounds. ``None`` unless at least half of the rays find the edge.
    """
    import cv2

    e = (cx, cy, r, r, 0.0)
    chosen: list[tuple[float, float]] = []
    for _ in range(4):
        peaks = _ray_peaks(mag, e[0], e[1], 0.75 * e[3], 1.25 * e[2])
        tol = max(1.0, 0.04 * e[2])
        chosen = []
        for ray, items in peaks.items():
            ang = 2 * math.pi * ray / RAYS
            want = _ellipse_radius(e, ang) if e[2] != e[3] else e[2]
            # the ray starts at the current center: its radius is measured from there
            x, y, rr = min(items, key=lambda q: abs(q[2] - want))
            if abs(rr - want) <= tol:
                chosen.append((x, y))
        if len(chosen) < RAYS // 2:
            return None
        (fx, fy), (w, h), ang_deg = cv2.fitEllipseAMS(np.array(chosen, dtype=np.float32))
        a, b = max(w, h) / 2, min(w, h) / 2
        if not (math.isfinite(a) and b > 0):
            return None
        phi = math.radians(ang_deg + (90 if h > w else 0))
        e = (float(fx), float(fy), float(a), float(b), phi)
    pts = np.array(chosen)
    angs = np.arctan2(pts[:, 1] - e[1], pts[:, 0] - e[0])
    dist = np.hypot(pts[:, 0] - e[0], pts[:, 1] - e[1])
    model = np.array([_ellipse_radius(e, t) for t in angs])
    rms = float(np.sqrt(np.mean((dist - model) ** 2)))
    return Hole(e[0], e[1], 2 * e[2], rms, len(chosen), 2 * e[3], math.degrees(e[4]) % 180)


def _ransac_circles(
    edge: Points, radius_lo: float, radius_hi: float, tol: float, best: int = 4, trials: int = 6000
) -> list[tuple[float, float, float]]:
    """Circles through edge points (N × 2) by RANSAC, scored by how much of the circle has
    edge support (36 angular bins), so straight edges and short arcs lose to whole circles."""
    rng = np.random.default_rng(0)
    if len(edge) < 3:
        return []
    if len(edge) > 4000:
        edge = edge[rng.choice(len(edge), 4000, replace=False)]
    idx = rng.integers(0, len(edge), size=(trials, 3))
    a, b, c = edge[idx[:, 0]], edge[idx[:, 1]], edge[idx[:, 2]]
    d = 2 * (a[:, 0] * (b[:, 1] - c[:, 1]) + b[:, 0] * (c[:, 1] - a[:, 1]) + c[:, 0] * (a[:, 1] - b[:, 1]))
    ok = np.abs(d) > 1e-6
    a, b, c, d = a[ok], b[ok], c[ok], d[ok]
    sa, sb, sc = (a**2).sum(1), (b**2).sum(1), (c**2).sum(1)
    ux = (sa * (b[:, 1] - c[:, 1]) + sb * (c[:, 1] - a[:, 1]) + sc * (a[:, 1] - b[:, 1])) / d
    uy = (sa * (c[:, 0] - b[:, 0]) + sb * (a[:, 0] - c[:, 0]) + sc * (b[:, 0] - a[:, 0])) / d
    r = np.hypot(a[:, 0] - ux, a[:, 1] - uy)
    keep = (r >= radius_lo) & (r <= radius_hi)
    ux, uy, r = ux[keep], uy[keep], r[keep]
    scored: list[tuple[int, float, float, float]] = []
    for start in range(0, len(r), 500):  # in chunks, to bound memory
        cx, cy, rr = ux[start : start + 500], uy[start : start + 500], r[start : start + 500]
        dx = edge[None, :, 0] - cx[:, None]
        dy = edge[None, :, 1] - cy[:, None]
        inl = np.abs(np.hypot(dx, dy) - rr[:, None]) <= tol
        bins = ((np.arctan2(dy, dx) + math.pi) / (2 * math.pi) * 36).astype(int) % 36
        for k in range(len(rr)):
            coverage = len(np.unique(bins[k][inl[k]]))
            scored.append((coverage, float(cx[k]), float(cy[k]), float(rr[k])))
    scored.sort(reverse=True)
    out: list[tuple[float, float, float]] = []
    for cov, cx0, cy0, r0 in scored:
        if cov < 18:  # less than half a circle
            break
        if all(math.hypot(cx0 - x, cy0 - y) > 3 * tol or abs(r0 - q) > 3 * tol for x, y, q in out):
            out.append((cx0, cy0, r0))
        if len(out) >= best:
            break
    return out


def holes(
    image: BGR,
    scale: Scale,
    box: tuple[float, float, float, float],
    dia_min: float,
    dia_max: float,
    count: int = 4,
) -> list[Hole]:
    """Round features (holes, pads, screw heads) with a diameter between ``dia_min`` and
    ``dia_max`` (user units) inside ``box``: up to ``count`` holes, each with all its rings.

    Starting circles come from RANSAC on the box's edges (whole circles beat straight edges
    and short arcs) plus the box's center; each is tracked around at full resolution from
    sub-pixel gradient peaks on rays and fitted as an ellipse. Concentric edges of one hole
    (the wall, a plating or mask ring) are grouped as one hole's rings, numbered from the
    inside out, so the same edge gets the same label in every photo; holes are numbered by
    their best-supported ring.
    """
    import cv2

    u0, v0, u1, v1 = _box_px(scale, box, image.shape)
    gray = cv2.cvtColor(image[v0:v1, u0:u1], cv2.COLOR_BGR2GRAY)
    radius_min = max(2.0, dia_min * scale.px_per_unit / 2)
    radius_max = max(radius_min + 1, dia_max * scale.px_per_unit / 2)
    k = min(1.0, 40 / ((radius_min + radius_max) / 2))  # RANSAC on a copy where the radii are ~40 px
    small = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    canny = cv2.Canny(cv2.GaussianBlur(small, (0, 0), 1.0), 40, 120)
    ys, xs = np.nonzero(canny)
    seeds = _ransac_circles(
        np.column_stack([xs, ys]).astype(np.float64), radius_min * k * 0.9, radius_max * k * 1.1, 1.5,
        count * 2,
    )  # fmt: skip
    candidates = [(x / k, y / k, r / k) for x, y, r in seeds]
    for frac in (0.25, 0.5, 0.75):  # and the box center, at a few radii
        candidates.append((gray.shape[1] / 2, gray.shape[0] / 2, radius_min + frac * (radius_max - radius_min)))
    blur = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), max(1.0, (radius_min + radius_max) / 200))
    mag = np.asarray(
        cv2.magnitude(cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)),
        dtype=np.float32,
    )
    fits: list[Hole] = []
    for cx, cy, r in candidates:
        h = _track(mag, cx, cy, r)
        if h and 1.8 * radius_min <= h.diameter <= 2.2 * radius_max and h.rms <= max(0.5, 0.01 * h.diameter):
            fits.append(h)
    fits.sort(key=lambda h: (-h.points, h.rms / h.diameter))
    unique: list[Hole] = []
    for h in fits:  # best-supported first; one per circle (another center, or another ring)
        if all(
            math.hypot(h.x - o.x, h.y - o.y) > 0.25 * o.diameter or abs(h.diameter - o.diameter) > 0.10 * o.diameter
            for o in unique
        ):
            unique.append(h)
    # group concentric rings into holes (in order of their best ring), rings inside out
    groups: list[list[Hole]] = []
    for h in unique:
        for g in groups:
            if math.hypot(h.x - g[0].x, h.y - g[0].y) < 0.25 * min(h.diameter, g[0].diameter):
                g.append(h)
                break
        else:
            groups.append([h])
    results = [
        replace(h, hole=n, ring=m)
        for n, g in enumerate(groups[:count], 1)
        for m, h in enumerate(sorted(g, key=lambda h: h.diameter), 1)
    ]
    out = []
    unit = scale.px_per_unit
    for h in results:
        center = scale.from_px(np.array([[h.x + u0, h.y + v0]]))[0]
        out.append(
            Hole(
                float(center[0]),
                float(center[1]),
                h.diameter / unit,
                h.rms / unit,
                h.points,
                h.minor / unit,
                h.angle_deg,
                h.hole,
                h.ring,
            )
        )
    return out


@dataclass(frozen=True)
class Outline:
    """A rectangular outline fitted to a part's edges (a rotated rectangle)."""

    x: float  #: center
    y: float
    length: float  #: along ``angle_deg``
    width: float  #: across it
    angle_deg: float  #: direction of the length side, counterclockwise from x
    rms: float  #: scatter of the edge points about the rectangle's sides
    points: dict[str, int]  #: edge points used per side (+L, -L along the length; +W, -W)
    corners: list[tuple[float, float]]  #: counterclockwise, starting at (-L/2, -W/2)


def _initial_rect(
    gray: npt.NDArray[np.uint8], dark: bool, open_px: int = 9
) -> tuple[tuple[float, float], tuple[float, float], float, npt.NDArray[np.float64]]:
    """The largest dark (or light) blob near the middle of ``gray``: cv2.minAreaRect and its
    outline points; thin things (a lever, shadow slivers) are opened away first."""
    import cv2

    blur = cv2.GaussianBlur(gray, (0, 0), 2)
    mode = cv2.THRESH_BINARY_INV if dark else cv2.THRESH_BINARY
    _, mask = cv2.threshold(blur, 0, 255, mode + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    filled = np.zeros_like(mask)  # fill holes (print, pads) so the part is one blob
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(filled, cs, -1, 255, -1)
    k = np.ones((open_px, open_px), np.uint8)
    mask = cv2.morphologyEx(filled, cv2.MORPH_OPEN, k)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("no part found in the box (try --light for a light part)")
    h, w = gray.shape
    center = np.array([w / 2, h / 2])

    def score(c: Any) -> float:
        m = cv2.moments(c)
        if not m["m00"]:
            return -1.0
        c_xy = np.array([m["m10"] / m["m00"], m["m01"] / m["m00"]])
        area = float(m["m00"])
        return area / (1.0 + float(np.hypot(*(c_xy - center))) / float(max(w, h)))

    best = max(contours, key=score)
    (cx, cy), (rw, rh), ang = cv2.minAreaRect(best)
    dense, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pts = max(dense, key=lambda c: cv2.pointPolygonTest(c, (cx, cy), False)).reshape(-1, 2)
    return (float(cx), float(cy)), (float(rw), float(rh)), float(ang), pts.astype(np.float64)


def fit_rectangle(
    sides: dict[str, list[npt.NDArray[np.float64]]], theta: float, tol: float = 0.0
) -> tuple[float, dict[str, float], npt.NDArray[np.float64], dict[str, int]]:
    """One rectangle through edge points grouped by side: ``+a``/``-a`` (normals ±n1) and
    ``+b``/``-b`` (normals ±n2), with n1 = (cos θ, sin θ), n2 = (−sin θ, cos θ).

    Each side is the line n·p = d. Alternately fits the four offsets d (means) and a small
    rotation (linearized: turning by dθ changes a point's residual by (dn/dθ)·p, with
    dn1/dθ = n2 and dn2/dθ = −n1), dropping points beyond 3 RMS. Returns θ, the offsets, the
    kept residuals and the points kept per side. With ``tol``, each side starts from the
    points within ``tol`` of its most common offset (where a component overhangs part of a
    side, those points are dropped) and later never keeps a point beyond 2 × ``tol``.
    """
    names = list(sides)
    pts = [(name, np.asarray(p, dtype=np.float64)) for name in names for p in sides[name]]
    keep = np.ones(len(pts), bool)
    if tol:  # keep, per side, the points near the most common offset (drop overhangs)
        th = theta
        n1 = np.array([math.cos(th), math.sin(th)])
        n2 = np.array([-math.sin(th), math.cos(th)])
        nrm = {"+a": n1, "-a": -n1, "+b": n2, "-b": -n2}
        proj = np.array([nrm[tag] @ p for tag, p in pts])
        tags = np.array([tag for tag, _ in pts])
        for name in names:
            sel = tags == name
            if not sel.any():
                continue
            v = proj[sel]
            counts_near = [(np.abs(v - x) <= tol).sum() for x in v]
            mode = v[int(np.argmax(counts_near))]
            keep[sel] = np.abs(v - mode) <= tol

    def normals(th: float) -> dict[str, tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]:
        n1 = np.array([math.cos(th), math.sin(th)])
        n2 = np.array([-math.sin(th), math.cos(th)])
        return {"+a": (n1, n2), "-a": (-n1, -n2), "+b": (n2, -n1), "-b": (-n2, n1)}  # n, dn/dθ

    for _ in range(8):
        nn = normals(theta)
        offsets = {
            name: float(
                np.mean([nn[name][0] @ p for (tag, p), ok in zip(pts, keep, strict=True) if tag == name and ok])
            )
            for name in names
        }
        resid = np.array([nn[tag][0] @ p - offsets[tag] for tag, p in pts])
        grad = np.array([nn[tag][1] @ p for tag, p in pts])
        for name in names:  # the offsets absorb a side's mean: center the gradient per side
            sel = np.array([tag == name for tag, _ in pts]) & keep
            if sel.any():
                grad[np.array([tag == name for tag, _ in pts])] -= grad[sel].mean()
        g, r = grad[keep], resid[keep]
        angle_step = -float(np.sum(r * g) / np.sum(g * g)) if np.sum(g * g) > 0 else 0.0
        theta += angle_step
        sigma = float(np.sqrt(np.mean(r**2))) if len(r) else 0.0
        keep = np.abs(resid) <= max(3 * sigma, 0.75)
        if tol:
            keep &= np.abs(resid) <= 2 * tol
        if abs(angle_step) < 1e-7:
            break
    nn = normals(theta)
    offsets = {
        name: float(np.mean([nn[name][0] @ p for (tag, p), ok in zip(pts, keep, strict=True) if tag == name and ok]))
        for name in names
    }
    resid = np.array([nn[tag][0] @ p - offsets[tag] for (tag, p), ok in zip(pts, keep, strict=True) if ok])
    counts = {
        name: int(sum(1 for (tag, _), ok in zip(pts, keep, strict=True) if tag == name and ok)) for name in names
    }
    return theta, offsets, resid, counts


def outline(
    image: BGR,
    scale: Scale,
    box: tuple[float, float, float, float],
    dark: bool = True,
    per_side: int = 16,
    min_strength: float = 8,
    band: float = 7,
    guess: tuple[float, float, float, float, float] | None = None,
    avoid: list[tuple[float, float, float, float]] | None = None,
    search: tuple[float, float] = (0.6, 1.0),
    span: float = 0.7,
) -> tuple[Outline, dict[str, list[tuple[float, float]]]]:
    """Fit a rotated rectangle to the outline of the part inside ``box`` (user units).

    The part is thresholded (the largest dark blob, or light with ``dark=False``; holes
    filled, thin parts such as a lever opened away) and a rectangle is fitted to its outline,
    each side taking the points near its most common offset, so a component or a shadow that
    overhangs part of a side is dropped. Then ``per_side`` short lines cross each side away
    from the corners (chamfers), from just outside, and take the first background-to-part
    edge to sub-pixel; one rectangle (common angle) is fitted to those the same way.

    ``guess`` (center x, y, length, width, angle of the length side in degrees) replaces the
    thresholding; ``avoid`` boxes (x0, y0, x1, y1) keep measuring lines away from components
    that overhang a side; ``search`` is how far outside and inside the first fit each line
    reaches; ``span`` is the share of each side the lines cover (the rest: corners). Returns
    the outline and the edge points used, per side (user units).
    """
    import cv2

    u0, v0, u1, v1 = _box_px(scale, box, image.shape)
    gray = cv2.cvtColor(image[v0:v1, u0:u1], cv2.COLOR_BGR2GRAY)
    unit = scale.px_per_unit  # px per user unit
    open_px = max(3, round(3.0 * unit)) if scale.rect else 15  # ~3 mm: drops levers, shadows
    tol = max(2.0, 0.3 * unit)  # ~0.3 mm
    if guess:
        gx, gy, glen, gwid, gang = guess
        (gcx, gcy), tip = scale.to_px(
            np.array([[gx, gy], [gx + math.cos(math.radians(gang)), gy + math.sin(math.radians(gang))]])
        )
        theta = math.atan2(tip[1] - gcy, tip[0] - gcx)
        n1 = np.array([math.cos(theta), math.sin(theta)])
        n2 = np.array([-math.sin(theta), math.cos(theta)])
        c0 = np.array([gcx, gcy])
        ha, hb = glen * unit / 2, gwid * unit / 2
        fitted = {
            "+a": n1 @ c0 + ha,
            "-a": -(n1 @ c0) + ha,
            "+b": n2 @ c0 + hb,
            "-b": -(n2 @ c0) + hb,
        }
    else:
        (cx, cy), (rw, rh), ang, contour = _initial_rect(np.asarray(gray, np.uint8), dark, open_px)
        theta = math.radians(ang)
        c0 = np.array([cx + u0, cy + v0])
        n1 = np.array([math.cos(theta), math.sin(theta)])
        n2 = np.array([-math.sin(theta), math.cos(theta)])
        # 1) the blob's outline points, by side of the first guess, away from the corners
        sides: dict[str, list[npt.NDArray[np.float64]]] = {"+a": [], "-a": [], "+b": [], "-b": []}
        for q in contour + np.array([u0, v0]):
            d = q - c0
            a_, b_ = d @ n1 / (rw / 2), d @ n2 / (rh / 2)
            if abs(a_) >= abs(b_) and abs(b_) < 0.7:
                sides["+a" if a_ > 0 else "-a"].append(q.astype(np.float64))
            elif abs(b_) > abs(a_) and abs(a_) < 0.7:
                sides["+b" if b_ > 0 else "-b"].append(q.astype(np.float64))
        if any(len(v) < 3 for v in sides.values()):
            raise ValueError("the part's outline was not found; check the box and --light/--dark")
        theta, fitted, _, _ = fit_rectangle(sides, theta, tol)
    # 2) sub-pixel: short lines across each fitted side, from outside, first part edge
    polarity = "falling" if dark else "rising"  # background → part
    n1 = np.array([math.cos(theta), math.sin(theta)])
    n2 = np.array([-math.sin(theta), math.cos(theta)])
    center = n1 * (fitted["+a"] - fitted["-a"]) / 2 + n2 * (fitted["+b"] - fitted["-b"]) / 2
    half = {"+a": (fitted["+a"] + fitted["-a"]) / 2, "+b": (fitted["+b"] + fitted["-b"]) / 2}
    half["-a"], half["-b"] = half["+a"], half["+b"]
    out_px, in_px = max(4.0, search[0] * unit), max(6.0, search[1] * unit)
    avoid_px = [
        (min(a[0], a[2]), min(a[1], a[3]), max(a[0], a[2]), max(a[1], a[3]))
        for a in (tuple(scale.to_px(np.array([[b[0], b[1]], [b[2], b[3]]])).ravel()) for b in avoid or [])
    ]

    def avoided(q: npt.NDArray[np.float64]) -> bool:
        return any(x0 <= q[0] <= x1 and y0 <= q[1] <= y1 for x0, y0, x1, y1 in avoid_px)

    fine: dict[str, list[npt.NDArray[np.float64]]] = {}
    for name, normal, along, half_along in (
        ("+a", n1, n2, half["+b"]),
        ("-a", -n1, n2, half["+b"]),
        ("+b", n2, n1, half["+a"]),
        ("-b", -n2, n1, half["+a"]),
    ):
        pts = []
        for f in np.linspace(-span, span, per_side):
            base = center + along * f * half_along + normal * half[name]
            if avoided(base):
                continue
            s_user, e_user = scale.from_px(np.array([base + normal * out_px, base - normal * in_px]))
            found = edges(image, scale, tuple(s_user), tuple(e_user), band, 1, min_strength, True, polarity)
            if found:
                pts.append(scale.to_px(np.array([[found[0].x, found[0].y]]))[0])
        fine[name] = pts
    sides = fine
    if any(len(v) < 3 for v in sides.values()):
        raise ValueError("too few edge points on a side; check the box and --light/--dark")
    theta, offsets, resid, counts = fit_rectangle(sides, theta, tol)
    n1 = np.array([math.cos(theta), math.sin(theta)])
    n2 = np.array([-math.sin(theta), math.cos(theta)])
    length_a = offsets["+a"] + offsets["-a"]  # extent along n1
    length_b = offsets["+b"] + offsets["-b"]  # extent along n2
    center_px = n1 * (offsets["+a"] - offsets["-a"]) / 2 + n2 * (offsets["+b"] - offsets["-b"]) / 2
    corners_px = [
        center_px + n1 * sa * length_a / 2 + n2 * sb * length_b / 2 for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    k = scale.px_per_unit
    center = scale.from_px(center_px[None, :])[0]
    corners = [(float(a), float(b)) for a, b in scale.from_px(np.array(corners_px))]
    # the length side and its angle in user coordinates (y up on rectified images)
    if length_a >= length_b:
        length, width, axis = length_a, length_b, n1
    else:
        length, width, axis = length_b, length_a, n2
    p0, p1 = scale.from_px(np.array([center_px, center_px + axis]))
    angle = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    angle = (angle + 90) % 180 - 90  # a side direction: −90…90
    used: dict[str, list[tuple[float, float]]] = {}
    for name, pts in sides.items():
        xy = scale.from_px(np.array(pts)) if pts else np.zeros((0, 2))
        used[name] = [(float(a), float(b)) for a, b in xy]
    return Outline(
        float(center[0]), float(center[1]), length / k, width / k, angle,
        float(np.sqrt(np.mean(resid**2))) / k, counts, corners,
    ), used  # fmt: skip
