"""A quick verdict on a set of photos, before anyone spends time measuring on them."""

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from cadder.photo.image import info, load
from cadder.photo.target import (
    DEFAULT_BOARD,
    Board,
    Camera,
    Rectification,
    detect,
    solve_pose,
)

MIN_CORNERS = 12
WARN_MM = 0.25  #: target fit error worth a warning
FAIL_MM = 0.5  #: target fit error that makes a photo unusable
MIN_ANGLE_DEG = 15.0  #: between the two most different views, for heights


@dataclass
class PhotoCheck:
    """One photo's verdict."""

    photo: str
    verdict: str  #: ok, warn or fail
    corners: int = 0
    fit_mm: float | None = None  #: the target's reprojection error, in mm on the paper
    tilt_deg: float | None = None
    reasons: list[str] = field(default_factory=list)


@dataclass
class SetCheck:
    """The verdict on a set of photos."""

    photos: list[PhotoCheck]
    angle_deg: float  #: the largest angle between two usable views
    notes: list[str]

    @property
    def ok(self) -> bool:
        """Whether enough photos are usable: two, or the only one given."""
        return sum(p.verdict != "fail" for p in self.photos) >= min(2, len(self.photos))


def camera_pose(photo: Path, board: Board, camera: Camera | None = None) -> Rectification:
    """A photo's camera pose from the target, without writing a rectified image."""
    image = load(photo)
    size = (image.shape[1], image.shape[0])
    obj, img = detect(image, board)
    if camera:
        if tuple(camera.image_size) != size:
            raise ValueError(f"{photo.name}: the camera file is for {camera.image_size} photos")
        k = np.asarray(camera.camera_matrix, dtype=np.float64)
        dist = np.asarray(camera.dist, dtype=np.float64)
        source = "camera"
    else:
        f = info(photo).focal_px
        if not f:
            raise ValueError(f"{photo.name}: no focal length in EXIF; make a camera file")
        k = np.array([[f, 0, size[0] / 2], [0, f, size[1] / 2], [0, 0, 1]], dtype=np.float64)
        dist = np.zeros(5)
        source = "exif"
    rvec, tvec, rms = solve_pose(obj, img, board, k, dist)

    def pose(corners: int, error: float) -> Rectification:
        return Rectification(
            source=photo.name,
            image_size=size,
            board=board,
            camera_matrix=k.tolist(),
            rvec=rvec.tolist(),
            tvec=tvec.tolist(),
            corners=corners,
            rms_px=error,
            focal={"used": float(k[0, 0]), "source": source},
            dist=dist.tolist(),
        )

    # a corner next to the part can be found in the wrong place: drop the far outliers
    keep = np.ones(len(obj), dtype=bool)
    for _ in range(3):
        errors = np.linalg.norm(pose(0, 0).project(obj) - img, axis=1)
        keep = errors <= max(3 * float(np.median(errors)), 3.0)
        if keep.sum() < 6:
            keep[:] = True
            break
        rvec, tvec, rms = solve_pose(obj[keep], img[keep], board, k, dist)
    return pose(int(keep.sum()), rms)


def _fit_mm(rect: Rectification) -> float:
    center = np.array([rect.board.width / 2, rect.board.height / 2, 0.0])
    steps = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0]])
    a, b, c = rect.project(center + steps)
    px_per_mm = math.sqrt(float(np.linalg.norm(b - a) * np.linalg.norm(c - a)))
    return rect.rms_px / px_per_mm


def check(photos: list[Path], board: Board = DEFAULT_BOARD, camera: Camera | None = None) -> SetCheck:
    """Look at each photo's target and at how different the viewing angles are."""
    results, directions = [], []
    for photo in photos:
        try:
            rect = camera_pose(photo, board, camera)
        except ValueError as exc:
            results.append(PhotoCheck(photo.name, "fail", reasons=[str(exc)]))
            continue
        result = PhotoCheck(photo.name, "ok", rect.corners, _fit_mm(rect), rect.tilt_deg)
        assert result.fit_mm is not None
        if result.corners < MIN_CORNERS:
            result.verdict = "fail"
            result.reasons.append(f"only {result.corners} target corners: show more of the target")
        if result.fit_mm > FAIL_MM:
            result.verdict = "fail"
            result.reasons.append(
                f"target fits only to {result.fit_mm:.2f} mm: flatten the paper, hold the phone still"
            )
        elif result.fit_mm > WARN_MM:
            result.verdict = "fail" if result.verdict == "fail" else "warn"
            result.reasons.append(f"target fits to {result.fit_mm:.2f} mm: is the paper flat?")
        results.append(result)
        if result.verdict != "fail":
            view = rect.camera_center - np.array([board.width / 2, board.height / 2, 0.0])
            directions.append(view / np.linalg.norm(view))
    angle = max(
        (math.degrees(math.acos(float(np.clip(a @ b, -1, 1)))) for a in directions for b in directions),
        default=0.0,
    )
    notes = []
    if len(photos) < 2:
        pass  # one photo measures a flat face: there are no angles to compare
    elif len(directions) < 2:
        notes.append("need at least two usable photos from different angles")
    elif angle < MIN_ANGLE_DEG:
        notes.append(f"views differ by only {angle:.0f}°: add one from well to the side")
    if not camera:
        notes.append("no camera file: calibrate from these photos for better numbers")
    return SetCheck(results, angle, notes)
