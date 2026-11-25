"""The printed ChArUco target and rectifying photos onto it.

A ChArUco board is a checkerboard with ArUco markers in its white squares: OpenCV finds its
corners to a fraction of a pixel and knows which corner each one is, even when the part lying
on it hides some of them. From the corners of one photo, :func:`rectify` gets the camera's
pose (and, if the photo has no usable EXIF, its focal length) and resamples the photo into a
square-on image of a plane parallel to the target, at a known number of pixels per mm.

**Target frame** (all millimeters here): origin at the board's bottom-left corner as printed
(the label is below the board), x to the right, y up, z up out of the paper. A point at height
``h`` above the paper has ``z = h``. OpenCV's own board frame has y down and z into the paper;
the conversion stays inside this module.
"""

import json
import math
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import numpy.typing as npt

from cadder.photo.image import BGR, info, load, save

if TYPE_CHECKING:
    import cv2

Points = npt.NDArray[np.float64]

#: Paper sizes (mm, portrait) for the printed target.
PAPER = {"A4": (210.0, 297.0), "LETTER": (215.9, 279.4), "A3": (297.0, 420.0)}


@dataclass(frozen=True)
class Board:
    """A ChArUco board: squares along x and y, the square and marker sizes, the dictionary.

    The default fits A4 with margins: 12 × 17 squares of 15 mm (180 × 255 mm). Printers scale:
    measure the printed squares (``square_mm``) and pass the measured value to ``rectify``.

    ``field`` leaves a plain white area for the part, as squares (x0, y0, x1, y1) counted from
    the bottom-left (x0 ≤ x < x1, y0 ≤ y < y1): a dark part's edges disappear over the black
    squares. Only the print uses it; detection finds the corners around it.
    """

    squares_x: int = 12
    squares_y: int = 17
    square_mm: float = 15.0
    marker_mm: float = 11.0
    dictionary: str = "DICT_5X5_250"
    field: tuple[int, int, int, int] | None = (3, 4, 9, 13)

    @property
    def field_mm(self) -> tuple[float, float, float, float] | None:
        """The white field in target mm (x0, y0, x1, y1), or ``None``."""
        if not self.field:
            return None
        return tuple(v * self.square_mm for v in self.field)  # type: ignore[return-value]

    @property
    def width(self) -> float:
        """Board width (x) in mm."""
        return self.squares_x * self.square_mm

    @property
    def height(self) -> float:
        """Board height (y) in mm."""
        return self.squares_y * self.square_mm

    def opencv(self) -> cv2.aruco.CharucoBoard:
        """The board as an OpenCV object (units: mm)."""
        import cv2

        dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, self.dictionary))
        return cv2.aruco.CharucoBoard(
            (self.squares_x, self.squares_y), self.square_mm, self.marker_mm, dictionary
        )

    def label(self) -> str:
        """One-line description printed under the board."""
        text = (
            f"cadder ChArUco {self.squares_x}x{self.squares_y}, square {self.square_mm:g} mm, "
            f"marker {self.marker_mm:g} mm, {self.dictionary}"
        )
        if self.field:
            text += ", field " + ",".join(str(v) for v in self.field)
        return text


DEFAULT_BOARD = Board()  #: the board ``cadder photo target`` prints by default


def make_target(
    path: Path, board: Board = DEFAULT_BOARD, paper: str = "A4", px_per_mm: float = 20.0
) -> Path:
    """Write a printable PDF of ``board`` on ``paper``, centered, with a label and a scale bar.

    Print it at 100 % (no "fit to page"), then measure 10 squares with a caliper.
    """
    from PIL import Image

    page = target_page(board, paper, px_per_mm)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(page).save(path, "PDF", resolution=25.4 * px_per_mm)
    return path


def target_page(
    board: Board = DEFAULT_BOARD, paper: str = "A4", px_per_mm: float = 20.0
) -> npt.NDArray[np.uint8]:
    """The target page as a grayscale image at ``px_per_mm``."""
    import cv2

    paper_w, paper_h = PAPER[paper.upper()]
    if board.width > paper_w - 10 or board.height > paper_h - 25:
        raise ValueError(f"{board.width:g} × {board.height:g} mm board does not fit {paper}")
    page = np.full((round(paper_h * px_per_mm), round(paper_w * px_per_mm)), 255, np.uint8)
    bw, bh = round(board.width * px_per_mm), round(board.height * px_per_mm)
    art = board.opencv().generateImage((bw, bh), marginSize=0, borderBits=1)
    if board.field:  # a plain white area for the part (rows count from the top in the image)
        fx0, fy0, fx1, fy1 = board.field
        sq = bw / board.squares_x
        art[round((board.squares_y - fy1) * sq) : round((board.squares_y - fy0) * sq),
            round(fx0 * sq) : round(fx1 * sq)] = 255  # fmt: skip
    x0 = (page.shape[1] - bw) // 2
    y0 = round(8 * px_per_mm)
    page[y0 : y0 + bh, x0 : x0 + bw] = art

    def text(s: str, x_mm: float, y_mm: float, size: float = 0.9) -> None:
        cv2.putText(
            page,
            s,
            (round(x_mm * px_per_mm), round(y_mm * px_per_mm)),
            cv2.FONT_HERSHEY_SIMPLEX,
            size * px_per_mm / 20 * 1.2,
            0,
            max(1, round(px_per_mm / 10)),
            cv2.LINE_AA,
        )

    left_mm, bottom_mm = x0 / px_per_mm, (y0 + bh) / px_per_mm
    text(board.label(), left_mm, bottom_mm + 5)
    text(
        "Print at 100 % (no fit to page). Measure 10 squares; pass square size to rectify.",
        left_mm,
        bottom_mm + 9,
        0.75,
    )
    origin = "origin (0,0): this corner, x right, y up, z up"
    if board.field_mm:
        origin += "; white field x {:g}-{:g}, y {:g}-{:g} mm".format(
            *board.field_mm[::2], *board.field_mm[1::2]
        )
    text(origin, left_mm, bottom_mm + 13, 0.75)
    bar_y = round((bottom_mm + 17) * px_per_mm)
    bar_x0 = x0
    for i in range(11):  # 100 mm scale bar with a tick every 10 mm
        x = bar_x0 + round(i * 10 * px_per_mm)
        tick = round((2 if i % 5 else 3.5) * px_per_mm)
        cv2.line(page, (x, bar_y - tick), (x, bar_y), 0, max(1, round(px_per_mm / 10)))
    cv2.line(page, (bar_x0, bar_y), (bar_x0 + round(100 * px_per_mm), bar_y), 0, 2)
    text("100 mm", left_mm + 102, bottom_mm + 17, 0.75)
    return page


def _to_cv(board: Board, points: Points) -> Points:
    """Target-frame points (x right, y up, z up) → OpenCV board frame (y down, z in)."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3).copy()
    p[:, 1] = board.height - p[:, 1]
    p[:, 2] = -p[:, 2]
    return p


def _from_cv(board: Board, points: Points) -> Points:
    """OpenCV board-frame points → target frame (the same flip both ways)."""
    return _to_cv(board, points)


def detect(image: BGR, board: Board) -> tuple[Points, Points]:
    """The board corners found in ``image``: target-frame points (N × 3) and pixels (N × 2)."""
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # One marker next to a corner is enough: corners on the white field's edge have only one.
    charuco = cv2.aruco.CharucoParameters()
    charuco.minMarkers = 1
    charuco.tryRefineMarkers = True
    markers = cv2.aruco.DetectorParameters()  # a bit more tolerant of oblique close-ups
    markers.adaptiveThreshWinSizeMin, markers.adaptiveThreshWinSizeMax = 5, 75
    markers.adaptiveThreshWinSizeStep = 10
    markers.minMarkerPerimeterRate = 0.01
    markers.polygonalApproxAccuracyRate = 0.05
    markers.perspectiveRemovePixelPerCell = 8
    markers.perspectiveRemoveIgnoredMarginPerCell = 0.2
    detector = cv2.aruco.CharucoDetector(board.opencv(), charuco, markers)
    # Markers that fill much of a phone photo have soft edges at full size: try a few scales
    # and keep the one that finds the most corners, then refine those at full size.
    best: tuple[int, Any, Any, float] = (0, None, None, 1.0)
    for scale in (1.0, 0.5, 0.35, 0.25):
        img_s = (
            gray
            if scale == 1
            else cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        )
        corners, ids, _, _ = detector.detectBoard(img_s)
        n = 0 if ids is None else len(ids)
        if n > best[0]:
            best = (n, corners, ids, scale)
    found, corners, ids, scale = best
    if found < 6:
        raise ValueError(f"target not found: {found} ChArUco corners (need at least 6)")
    pts = np.asarray(corners, dtype=np.float32).reshape(-1, 1, 2)
    if scale != 1:
        pts = np.asarray(pts / np.float32(scale), dtype=np.float32)
        win = max(5, round(2 / scale))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.01)
        pts = np.asarray(cv2.cornerSubPix(gray, pts, (win, win), (-1, -1), criteria))
    corners = pts
    obj, img = cast(Any, board.opencv()).matchImagePoints(corners, ids)  # stubs: list only
    obj_cv = np.asarray(obj, dtype=np.float64).reshape(-1, 3)
    return _from_cv(board, obj_cv), np.asarray(img, dtype=np.float64).reshape(-1, 2)


@dataclass
class Rectification:
    """A photo's camera pose on the target and the rectified image made from it (JSON sidecar).

    ``rvec``/``tvec`` are OpenCV's pose of the board frame in camera coordinates; use the
    methods, which work in the target frame.
    """

    source: str  #: the photo, relative to the sidecar's folder
    image_size: tuple[int, int]  #: photo width, height (px)
    board: Board
    camera_matrix: list[list[float]]
    rvec: list[float]
    tvec: list[float]
    corners: int  #: ChArUco corners used
    rms_px: float  #: reprojection error of the pose
    focal: dict[str, float | str | None]  #: used, source (exif/fit/given), exif, fit
    plane_height: float = 0.0  #: the rectified plane's height above the paper (mm)
    px_per_mm: float = 0.0
    region: tuple[float, float, float, float] = (0, 0, 0, 0)  #: x0, y0, x1, y1 (target mm)
    image: str = ""  #: the rectified image's file name (next to the sidecar)
    notes: list[str] = field(default_factory=list)
    dist: list[float] = field(default_factory=lambda: [0.0] * 5)  #: lens distortion (OpenCV)

    # -- geometry --------------------------------------------------------------------------

    def _k(self) -> Points:
        return np.asarray(self.camera_matrix, dtype=np.float64)

    def _d(self) -> Points:
        return np.asarray(self.dist, dtype=np.float64)

    def _rt(self) -> tuple[Points, Points]:
        import cv2

        r, _ = cv2.Rodrigues(np.asarray(self.rvec, dtype=np.float64))
        return np.asarray(r, dtype=np.float64), np.asarray(self.tvec, dtype=np.float64)

    def project(self, points: Points) -> Points:
        """Target-frame points (N × 3, mm) → photo pixels (N × 2)."""
        import cv2

        obj = _to_cv(self.board, points)
        px, _ = cv2.projectPoints(
            obj, np.asarray(self.rvec), np.asarray(self.tvec), self._k(), self._d()
        )
        return np.asarray(px, dtype=np.float64).reshape(-1, 2)

    def to_plane(self, pixels: Points, height: float = 0.0) -> Points:
        """Photo pixels (N × 2) → target-frame points (N × 2, mm) on the plane ``z = height``.

        This is the parallax correction: a feature at ``height`` above the paper seen at a pixel
        lies where the camera's ray through that pixel meets that plane.
        """
        import cv2

        px = np.asarray(pixels, dtype=np.float64).reshape(-1, 1, 2)
        norm = cv2.undistortPoints(px, self._k(), self._d()).reshape(-1, 2)  # lens removed
        rays = np.column_stack([norm, np.ones(len(norm))])
        r, t = self._rt()
        center = -r.T @ t  # camera center, board frame
        dirs = rays @ r  # = (r.T @ rays.T).T
        z = -height  # board frame: z into the paper
        s = (z - center[2]) / dirs[:, 2]
        hit = center + dirs * s[:, None]
        return _from_cv(self.board, hit)[:, :2]

    def ray(self, pixels: Points) -> tuple[Points, Points]:
        """Camera rays through photo pixels, in the target frame: origin (3,) and unit
        directions (N × 3)."""
        import cv2

        px = np.asarray(pixels, dtype=np.float64).reshape(-1, 1, 2)
        norm = cv2.undistortPoints(px, self._k(), self._d()).reshape(-1, 2)
        r, _ = self._rt()
        dirs_cv = np.column_stack([norm, np.ones(len(norm))]) @ r
        dirs = dirs_cv * np.array([1.0, -1.0, -1.0])  # board frame → target frame (no shift)
        return self.camera_center, dirs / np.linalg.norm(dirs, axis=1, keepdims=True)

    @property
    def camera_center(self) -> Points:
        """Camera position in the target frame (mm)."""
        r, t = self._rt()
        return np.asarray(_from_cv(self.board, -r.T @ t)[0], dtype=np.float64)

    @property
    def tilt_deg(self) -> float:
        """Angle between the camera's axis and the target's normal (0 = square-on)."""
        r, _ = self._rt()
        axis = r.T @ np.array([0.0, 0.0, 1.0])  # camera z in the board frame
        return math.degrees(math.acos(min(1.0, abs(axis[2]))))

    def rect_to_mm(self, uv: Points) -> Points:
        """Rectified-image pixels (N × 2) → target mm on the rectified plane."""
        p = np.asarray(uv, dtype=np.float64).reshape(-1, 2)
        x0, _, _, y1 = self.region
        return np.column_stack([x0 + p[:, 0] / self.px_per_mm, y1 - p[:, 1] / self.px_per_mm])

    def mm_to_rect(self, xy: Points) -> Points:
        """Target mm (N × 2) on the rectified plane → rectified-image pixels."""
        p = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
        x0, _, _, y1 = self.region
        return np.column_stack([(p[:, 0] - x0) * self.px_per_mm, (y1 - p[:, 1]) * self.px_per_mm])

    def rect_to_photo(self, uv: Points) -> Points:
        """Rectified-image pixels → photo pixels."""
        xy = self.rect_to_mm(uv)
        return self.project(np.column_stack([xy, np.full(len(xy), self.plane_height)]))

    def photo_to_rect(self, px: Points) -> Points:
        """Photo pixels → rectified-image pixels."""
        return self.mm_to_rect(self.to_plane(px, self.plane_height))

    def rect_maps(self, size: tuple[int, int], step: int = 8) -> tuple[Any, Any]:
        """``cv2.remap`` maps from a rectified image of ``size`` (w, h) to photo pixels:
        projected exactly on a coarse grid (every ``step`` px) and interpolated bilinearly in
        between, which is ample for the smooth lens and perspective mapping."""
        import cv2

        w, h = size
        us = np.arange(0, w + step, step, dtype=np.float64)
        vs = np.arange(0, h + step, step, dtype=np.float64)
        grid = np.stack(np.meshgrid(us, vs), axis=-1).reshape(-1, 2)
        photo = self.rect_to_photo(grid).reshape(len(vs), len(us), 2).astype(np.float32)
        # sample the coarse grid bilinearly at u / step, v / step for every output pixel
        cu, cv = np.meshgrid(
            np.arange(w, dtype=np.float32) / step, np.arange(h, dtype=np.float32) / step
        )
        map_x = cv2.remap(photo[..., 0], cu, cv, cv2.INTER_LINEAR)
        map_y = cv2.remap(photo[..., 1], cu, cv, cv2.INTER_LINEAR)
        return map_x, map_y

    def at_height(self, xy: Points, height: float) -> Points:
        """Rectified-plane mm of features that are really at ``height``: their true x, y (mm).

        A feature seen at ``xy`` in the rectified image lies on the camera ray through that
        point; this returns where that ray meets ``z = height``.
        """
        xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
        on_plane = np.column_stack([xy, np.full(len(xy), self.plane_height)])
        return self.to_plane(self.project(on_plane), height)

    # -- persistence -----------------------------------------------------------------------

    def to_json(self) -> str:
        """The sidecar's JSON text."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> Rectification:
        """Read a sidecar's JSON text."""
        data: dict[str, Any] = json.loads(text)
        board = data["board"]
        if board.get("field") is not None:
            board["field"] = tuple(board["field"])
        data["board"] = Board(**board)
        data["image_size"] = tuple(data["image_size"])
        data["region"] = tuple(data["region"])
        return cls(**data)

    @classmethod
    def load(cls, path: Path) -> Rectification:
        """Read a sidecar file."""
        return cls.from_json(path.read_text())


def triangulate(views: list[tuple[Rectification, Points]]) -> tuple[Points, float]:
    """A feature's 3D position (target frame) from where it is seen in two or more photos:
    each view is a rectification and the feature's position on its rectified plane (mm).
    Returns the point closest to all the rays and the RMS distance of the rays from it (mm)."""
    a = np.zeros((3, 3))
    b = np.zeros(3)
    rays = []
    for rect, xy in views:
        xy = np.asarray(xy, dtype=np.float64).reshape(1, 2)
        px = rect.project(np.column_stack([xy, [rect.plane_height]]))
        origin, d = rect.ray(px)
        d = d[0]
        m = np.eye(3) - np.outer(d, d)
        a += m
        b += m @ origin
        rays.append((origin, d))
    point = np.linalg.solve(a, b)
    miss = [np.linalg.norm((np.eye(3) - np.outer(d, d)) @ (point - o)) for o, d in rays]
    return point, float(np.sqrt(np.mean(np.square(miss))))


def sidecar_for(image: Path) -> Path | None:
    """The sidecar of a rectified image (``x.rect.png`` → ``x.rect.json``), if there is one."""
    candidate = image.with_suffix(".json")
    return candidate if image.suffix == ".png" and candidate.exists() else None


def _fit_focal(obj: Points, img: Points, size: tuple[int, int], guess: float) -> float | None:
    """Focal length (px) fitted from one view of the board, principal point fixed at the
    center; ``None`` when the fit fails (a square-on view barely constrains it)."""
    import cv2

    w, h = size
    k0 = np.array([[guess, 0, w / 2], [0, guess, h / 2], [0, 0, 1]], dtype=np.float64)
    flags = (
        cv2.CALIB_USE_INTRINSIC_GUESS
        | cv2.CALIB_FIX_PRINCIPAL_POINT
        | cv2.CALIB_FIX_ASPECT_RATIO
        | cv2.CALIB_ZERO_TANGENT_DIST
        | cv2.CALIB_FIX_K1
        | cv2.CALIB_FIX_K2
        | cv2.CALIB_FIX_K3
    )
    try:
        _, k, _, _, _ = cv2.calibrateCamera(
            [obj_cv(obj)],
            [img.astype(np.float32)],
            size,
            k0,
            np.zeros(5),
            flags=flags,
        )
    except cv2.error:
        return None
    f = float(k[0, 0])
    return f if math.isfinite(f) and f > 0 else None


def obj_cv(points: Points) -> Points:
    """Board points for OpenCV calibration: any planar frame works, so the target frame's
    x, y with z = 0 (calibration needs the board plane at z = 0)."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3).copy()
    p[:, 2] = 0
    return p.astype(np.float32)


def solve_pose(
    obj: Points, img: Points, board: Board, k: Points, dist: Points | None = None
) -> tuple[Points, Points, float]:
    """Camera pose (rvec, tvec in OpenCV's board frame) and RMS reprojection error (px)."""
    import cv2

    d = np.zeros(5) if dist is None else dist
    obj_b = _to_cv(board, obj)
    ok, rvec, tvec = cv2.solvePnP(obj_b, img, k, d, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        raise ValueError("could not solve the camera pose from the target")
    rvec, tvec = cv2.solvePnPRefineLM(obj_b, img, k, d, rvec, tvec)
    proj, _ = cv2.projectPoints(obj_b, rvec, tvec, k, d)
    rms = float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - img) ** 2, axis=1))))
    return np.asarray(rvec, np.float64).ravel(), np.asarray(tvec, np.float64).ravel(), rms


def fit_distortion(obj: Points, img: Points, size: tuple[int, int], k: Points) -> Points | None:
    """Radial lens distortion (k1, k2) fitted from one view with the focal length and the
    principal point held fixed; ``None`` if the fit fails."""
    import cv2

    flags = (
        cv2.CALIB_USE_INTRINSIC_GUESS
        | cv2.CALIB_FIX_FOCAL_LENGTH
        | cv2.CALIB_FIX_PRINCIPAL_POINT
        | cv2.CALIB_FIX_ASPECT_RATIO
        | cv2.CALIB_ZERO_TANGENT_DIST
        | cv2.CALIB_FIX_K3
    )
    try:
        _, _, dist, _, _ = cv2.calibrateCamera(
            [obj_cv(obj)], [img.astype(np.float32)], size, k.copy(), np.zeros(5), flags=flags
        )
    except cv2.error:
        return None
    d = np.asarray(dist, dtype=np.float64).ravel()[:5]
    return d if np.all(np.isfinite(d)) else None


@dataclass
class Camera:
    """A calibrated camera (one phone at one zoom): focal length, principal point, distortion."""

    camera_matrix: list[list[float]]
    dist: list[float]
    image_size: tuple[int, int]
    rms_px: float  #: reprojection error over all calibration views
    views: list[dict[str, Any]] = field(default_factory=list)  #: per photo: name, corners, rms

    def to_json(self) -> str:
        """The camera file's JSON text."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def load(cls, path: Path) -> Camera:
        """Read a camera file."""
        data: dict[str, Any] = json.loads(path.read_text())
        data["image_size"] = tuple(data["image_size"])
        return cls(**data)


def calibrate(photos: list[Path], board: Board = DEFAULT_BOARD) -> Camera:
    """Calibrate the camera from several photos of the target (same phone, same zoom).

    Each photo adds a view of the target from another angle; together they pin down the
    focal length and the lens distortion far better than one photo can. Fits the focal length
    (one, square pixels), the principal point and radial distortion k1, k2 (k3 when there are
    many corners).
    """
    import cv2

    objs, imgs, names, size = [], [], [], None
    guess = None
    for p in photos:
        image = load(p)
        s = (image.shape[1], image.shape[0])
        if size and s != size:
            raise ValueError(f"{p.name}: {s[0]}×{s[1]}, but the others are {size[0]}×{size[1]}")
        size = s
        try:
            obj, img = detect(image, board)
        except ValueError as exc:
            raise ValueError(f"{p.name}: {exc}") from exc
        objs.append(obj_cv(obj))
        imgs.append(img.astype(np.float32))
        names.append(p.name)
        guess = guess or info(p).focal_px
    if size is None or len(objs) < 2:
        raise ValueError("calibration needs at least two photos of the target")
    w, h = size
    f0 = guess or max(size)
    k0 = np.array([[f0, 0, w / 2], [0, f0, h / 2], [0, 0, 1]], dtype=np.float64)
    flags = cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_FIX_ASPECT_RATIO | cv2.CALIB_ZERO_TANGENT_DIST
    if sum(len(o) for o in objs) < 150:
        flags |= cv2.CALIB_FIX_K3
    for _ in range(4):  # drop misplaced corners (found next to the part) and fit again
        rms, k, dist, rvecs, tvecs = cv2.calibrateCamera(
            objs, imgs, size, k0.copy(), np.zeros(5), flags=flags
        )
        errors = []
        for o, i, rv, tv in zip(objs, imgs, rvecs, tvecs, strict=True):
            proj, _ = cv2.projectPoints(o, rv, tv, k, dist)
            errors.append(np.linalg.norm(proj.reshape(-1, 2) - i.reshape(-1, 2), axis=1))
        limit = max(3 * float(np.median(np.concatenate(errors))), 3.0)
        keep = [e <= limit if (e <= limit).sum() >= 6 else e >= 0 for e in errors]
        if all(m.all() for m in keep):
            break
        objs = [o[m] for o, m in zip(objs, keep, strict=True)]
        imgs = [i[m] for i, m in zip(imgs, keep, strict=True)]
    views = []
    for name, o, i, rv, tv in zip(names, objs, imgs, rvecs, tvecs, strict=True):
        proj, _ = cv2.projectPoints(o, rv, tv, k, dist)
        e = float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - i) ** 2, axis=1))))
        views.append({"photo": name, "corners": len(o), "rms_px": round(e, 3)})
    return Camera(
        camera_matrix=np.asarray(k, dtype=np.float64).tolist(),
        dist=np.asarray(dist, dtype=np.float64).ravel()[:5].tolist(),
        image_size=size,
        rms_px=float(rms),
        views=views,
    )


def rectify(
    photo: Path,
    out_dir: Path,
    board: Board = DEFAULT_BOARD,
    plane_height: float = 0.0,
    region: tuple[float, float, float, float] | None = None,
    px_per_mm: float | None = None,
    focal_px: float | None = None,
    camera: Camera | None = None,
) -> Rectification:
    """Rectify ``photo`` onto the plane ``z = plane_height`` of the target.

    Writes ``<stem>.rect.png`` (square-on, ``px_per_mm``, y up = image up) and its sidecar
    ``<stem>.rect.json`` to ``out_dir`` (``<stem>.h<H>.rect.*`` for a plane at height H, so
    rectifications of one photo at several heights sit side by side); returns the sidecar's
    data. ``region`` (target mm)
    defaults to the whole board; ``px_per_mm`` to the photo's own resolution at the board's
    center. The focal length comes from ``focal_px``, else the photo's EXIF, else a fit to the
    target (all three are reported). With ``camera`` (from :func:`calibrate`), its focal
    length, principal point and distortion are used as they are.
    """
    import cv2

    image = load(photo)
    size = (image.shape[1], image.shape[0])
    obj, img = detect(image, board)
    notes: list[str] = []
    if region:  # paper is rarely flat: solve from the corners nearest the region
        x0, y0, x1, y1 = region
        for squares in (2, 3, 4, 6):  # widen until there are enough (a white field has none)
            m = squares * board.square_mm
            near = (
                (obj[:, 0] >= x0 - m)
                & (obj[:, 0] <= x1 + m)
                & (obj[:, 1] >= y0 - m)
                & (obj[:, 1] <= y1 + m)
            )
            if near.sum() >= 20:
                break
        if near.sum() >= 12 and near.sum() < len(obj):
            notes.append(
                f"pose from the {int(near.sum())} of {len(obj)} corners within {squares} squares "
                "of the region"
            )
            obj, img = obj[near], img[near]
    exif_f = info(photo).focal_px
    fit_f = _fit_focal(obj, img, size, focal_px or exif_f or max(size))
    if camera and tuple(camera.image_size) != size:
        raise ValueError(f"the camera was calibrated for {camera.image_size}, the photo is {size}")
    if camera:
        used, source = float(camera.camera_matrix[0][0]), "camera"
    elif focal_px:
        used, source = focal_px, "given"
    elif exif_f:
        used, source = exif_f, "exif"
    elif fit_f:
        used, source = fit_f, "fit"
    else:
        raise ValueError("no focal length: no EXIF and the fit failed; pass --focal")
    k = np.array([[used, 0, size[0] / 2], [0, used, size[1] / 2], [0, 0, 1]], dtype=np.float64)
    dist = np.zeros(5)
    if camera:
        k = np.asarray(camera.camera_matrix, dtype=np.float64)
        dist = np.asarray(camera.dist, dtype=np.float64)
    rvec, tvec, rms = solve_pose(obj, img, board, k, dist)
    if not camera and rms > 0.8 and len(obj) >= 30:  # try a lens distortion model
        fitted = fit_distortion(obj, img, size, k)
        if fitted is not None:
            rvec2, tvec2, rms2 = solve_pose(obj, img, board, k, fitted)
            if rms2 < 0.7 * rms:
                notes.append(
                    f"lens distortion fitted (k1 {fitted[0]:.4f}, k2 {fitted[1]:.4f}): "
                    f"reprojection {rms:.2f} → {rms2:.2f} px"
                )
                rvec, tvec, rms, dist = rvec2, tvec2, rms2, fitted
    rect = Rectification(
        source=os.path.relpath(Path(photo).resolve(), Path(out_dir).resolve()),
        image_size=size,
        board=board,
        camera_matrix=k.tolist(),
        rvec=rvec.tolist(),
        tvec=tvec.tolist(),
        corners=len(obj),
        rms_px=rms,
        focal={"used": used, "source": source, "exif": exif_f, "fit": fit_f},
        plane_height=plane_height,
        region=region or (0.0, 0.0, board.width, board.height),
        notes=notes,
        dist=dist.tolist(),
    )
    if exif_f and fit_f and abs(fit_f / exif_f - 1) > 0.05 and rect.tilt_deg > 10:
        # (a near square-on view barely constrains the focal length: no note then)
        rect.notes.append(
            f"focal length: EXIF {exif_f:.0f} px vs fit {fit_f:.0f} px "
            f"({100 * (fit_f / exif_f - 1):+.1f} %); scale may be off by part of that"
        )
    cx, cy = (rect.region[0] + rect.region[2]) / 2, (rect.region[1] + rect.region[3]) / 2
    a, b = rect.project(np.array([[cx, cy, plane_height], [cx + 1, cy, plane_height]]))
    native = float(np.hypot(*(b - a)))  # the photo's own px per mm at the region's center
    if rms > 1.5:
        rect.notes.append(
            f"reprojection error {rms:.2f} px ({rms / native:.2f} mm) is high: paper not flat? "
            "Tape the target flat, or pass --region around the part"
        )
    px_per_mm = px_per_mm or round(native, 1)
    rect.px_per_mm = px_per_mm
    x0, y0, x1, y1 = rect.region
    out_size = (round((x1 - x0) * px_per_mm), round((y1 - y0) * px_per_mm))
    map_x, map_y = rect.rect_maps(out_size)
    out = cv2.remap(
        image, map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
        borderValue=(128, 128, 128),
    )  # fmt: skip
    stem = Path(photo).stem + (f".h{plane_height:g}" if plane_height else "") + ".rect"
    rect.image = stem + ".png"
    save(np.asarray(out, dtype=np.uint8), out_dir / rect.image)
    (out_dir / f"{stem}.json").write_text(rect.to_json())
    return rect


def with_square(board: Board, square_mm: float | None) -> Board:
    """``board`` with the printed (measured) square size; the marker scales with it."""
    if not square_mm:
        return board
    return replace(
        board, square_mm=square_mm, marker_mm=board.marker_mm * square_mm / board.square_mm
    )


def summary(rect: Rectification) -> str:
    """A few lines describing a rectification."""
    c = rect.camera_center
    f = rect.focal

    def px(value: float | str | None) -> str:
        return "-" if value is None else f"{float(value):.0f}"

    lines = [
        f"photo {rect.source}: {rect.corners} target corners, reprojection {rect.rms_px:.2f} px",
        f"focal {px(f['used'])} px ({f['source']}; exif {px(f['exif'])}, "
        + (f"fit {px(f['fit'])})" if rect.tilt_deg > 10 else "fit: view too square-on to tell)"),
        f"camera at ({c[0]:.0f}, {c[1]:.0f}, {c[2]:.0f}) mm, tilt {rect.tilt_deg:.1f}°",
        f"rectified plane z = {rect.plane_height:g} mm, {rect.px_per_mm:g} px/mm, region "
        + ", ".join(f"{v:g}" for v in rect.region)
        + f" mm → {rect.image}",
    ]
    lines += [f"note: {n}" for n in rect.notes]
    return "\n".join(lines)
