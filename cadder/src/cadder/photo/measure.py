"""Measuring on an image: enlarged crops with a coordinate grid, edges along a line, holes.

Coordinates are pixels of the image, or target millimeters when the image is a rectified one
(``Scale`` built from its sidecar). Every function returns plain numbers so an agent can use
them directly; the crop is for looking, the others are for numbers.
"""

import math
from dataclasses import dataclass, replace

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


def _box_px(
    scale: Scale, box: tuple[float, float, float, float], shape: tuple[int, ...]
) -> tuple[int, int, int, int]:
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
    out = cv2.resize(
        part, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC if k > 1 else cv2.INTER_AREA
    )
    (x0, y0), (x1, y1) = scale.from_px(np.array([[u0, v0], [u1, v1]], dtype=np.float64))
    xs, ys = sorted((x0, x1)), sorted((y0, y1))
    step = grid or nice_step(max(xs[1] - xs[0], ys[1] - ys[0]))
    font = cv2.FONT_HERSHEY_SIMPLEX
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
                cv2.putText(out, label, (x + 3, 16), font, 0.5, color, 1, cv2.LINE_AA)
            else:
                y = round((v - v0) * k)
                cv2.line(out, (0, y), (out.shape[1], y), color, 1)
                cv2.putText(out, label, (3, y - 4), font, 0.5, color, 1, cv2.LINE_AA)
    cv2.putText(out, scale.unit, (out.shape[1] - 40, out.shape[0] - 10), font, 0.6, (0, 0, 255), 1)
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
    peaks = [
        i
        for i in range(1, n - 1)
        if mag[i] >= mag[i - 1] and mag[i] > mag[i + 1] and mag[i] >= min_strength
    ]
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
    mag: npt.NDArray[np.float32], cx: float, cy: float, r_lo: float, r_hi: float
) -> dict[int, list[tuple[float, float, float]]]:
    """Gradient peaks on ``RAYS`` rays from (cx, cy) between radii ``r_lo`` and ``r_hi``:
    ray index → [(x, y, radius)], sub-pixel, every local maximum above a quarter of the ray's
    strongest."""
    import cv2

    n = max(32, round((r_hi - r_lo) * 2))
    radii = np.linspace(r_lo, r_hi, n)
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
    edge: Points, r_lo: float, r_hi: float, tol: float, best: int = 4, trials: int = 6000
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
    d = 2 * (
        a[:, 0] * (b[:, 1] - c[:, 1])
        + b[:, 0] * (c[:, 1] - a[:, 1])
        + c[:, 0] * (a[:, 1] - b[:, 1])
    )
    ok = np.abs(d) > 1e-6
    a, b, c, d = a[ok], b[ok], c[ok], d[ok]
    sa, sb, sc = (a**2).sum(1), (b**2).sum(1), (c**2).sum(1)
    ux = (sa * (b[:, 1] - c[:, 1]) + sb * (c[:, 1] - a[:, 1]) + sc * (a[:, 1] - b[:, 1])) / d
    uy = (sa * (c[:, 0] - b[:, 0]) + sb * (a[:, 0] - c[:, 0]) + sc * (b[:, 0] - a[:, 0])) / d
    r = np.hypot(a[:, 0] - ux, a[:, 1] - uy)
    keep = (r >= r_lo) & (r <= r_hi)
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
    d_min: float,
    d_max: float,
    count: int = 4,
) -> list[Hole]:
    """Round features (holes, pads, screw heads) with a diameter between ``d_min`` and
    ``d_max`` (user units) inside ``box``: up to ``count`` holes, each with all its rings.

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
    r_min = max(2.0, d_min * scale.px_per_unit / 2)
    r_max = max(r_min + 1, d_max * scale.px_per_unit / 2)
    k = min(1.0, 40 / ((r_min + r_max) / 2))  # RANSAC on a copy where the radii are ~40 px
    small = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    canny = cv2.Canny(cv2.GaussianBlur(small, (0, 0), 1.0), 40, 120)
    ys, xs = np.nonzero(canny)
    seeds = _ransac_circles(
        np.column_stack([xs, ys]).astype(np.float64), r_min * k * 0.9, r_max * k * 1.1, 1.5,
        count * 2,
    )  # fmt: skip
    candidates = [(x / k, y / k, r / k) for x, y, r in seeds]
    for frac in (0.25, 0.5, 0.75):  # and the box center, at a few radii
        candidates.append((gray.shape[1] / 2, gray.shape[0] / 2, r_min + frac * (r_max - r_min)))
    blur = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), max(1.0, (r_min + r_max) / 200))
    mag = np.asarray(
        cv2.magnitude(
            cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
        ),
        dtype=np.float32,
    )
    fits: list[Hole] = []
    for cx, cy, r in candidates:
        h = _track(mag, cx, cy, r)
        if h and 1.8 * r_min <= h.diameter <= 2.2 * r_max and h.rms <= max(0.5, 0.01 * h.diameter):
            fits.append(h)
    fits.sort(key=lambda h: (-h.points, h.rms / h.diameter))
    unique: list[Hole] = []
    for h in fits:  # best-supported first; one per circle (another center, or another ring)
        if all(
            math.hypot(h.x - o.x, h.y - o.y) > 0.25 * o.diameter
            or abs(h.diameter - o.diameter) > 0.10 * o.diameter
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
