"""cadder.photo on a synthetic photo: a target with a part on it, seen by a known camera."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from cadder.photo.features import overlay, read, table  # noqa: E402
from cadder.photo.image import info  # noqa: E402
from cadder.photo.measure import Scale, crop, edges, holes  # noqa: E402
from cadder.photo.target import (  # noqa: E402
    Board,
    Rectification,
    _to_cv,
    detect,
    make_target,
    rectify,
    target_page,
    with_square,
)

BOARD = Board()
PPM = 10  #: synthetic board art, px per mm
HOLE = (52.5, 67.5)  #: hole center on the target (mm)
HOLE_D = 6.0
RING_D = 9.0  #: a light ring around the hole on the dark plate
FOCAL = 3200.0
SIZE = (3000, 4000)
CAMERA = np.array([95.0, 130.0, 420.0])  #: camera position, target frame


def _art() -> np.ndarray:
    """The board as printed, with a light plate, a dark ring and a darker hole on it."""
    art = BOARD.opencv().generateImage(
        (round(BOARD.width * PPM), round(BOARD.height * PPM)), marginSize=0, borderBits=1
    )
    art = cv2.cvtColor(art, cv2.COLOR_GRAY2BGR)

    def px(x: float, y: float) -> tuple[int, int]:  # mm → art pixel (fixed point, shift 4)
        return round(x * PPM * 16 - 8), round((BOARD.height - y) * PPM * 16 - 8)

    cv2.rectangle(art, px(40, 80), px(70, 55), (170, 170, 170), -1, cv2.LINE_AA, 4)
    cv2.circle(
        art, px(*HOLE), round((RING_D / 2 * PPM - 0.5) * 16), (90, 90, 90), -1, cv2.LINE_AA, 4
    )
    cv2.circle(
        art, px(*HOLE), round((HOLE_D / 2 * PPM - 0.5) * 16), (25, 25, 25), -1, cv2.LINE_AA, 4
    )
    return art


def _pose() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Camera matrix, rvec and tvec (OpenCV board frame) of the synthetic camera."""
    k = np.array([[FOCAL, 0, SIZE[0] / 2], [0, FOCAL, SIZE[1] / 2], [0, 0, 1]])
    r, _ = cv2.Rodrigues(np.array([math.radians(12), math.radians(-5), 0.1]))
    center_cv = _to_cv(BOARD, CAMERA[None, :])[0]
    rvec, _ = cv2.Rodrigues(r)
    return k, rvec, -r @ center_cv


@pytest.fixture(scope="module")
def photo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The synthetic photo: the board art seen by the camera of ``_pose``."""
    folder = tmp_path_factory.mktemp("photo")
    k, rvec, tvec = _pose()
    corners = np.array(
        [[0, 0, 0], [BOARD.width, 0, 0], [BOARD.width, BOARD.height, 0], [0, BOARD.height, 0]]
    )
    img_px, _ = cv2.projectPoints(_to_cv(BOARD, corners), rvec, tvec, k, np.zeros(5))
    w, h = BOARD.width * PPM, BOARD.height * PPM
    art_px = np.array([[0, h], [w, h], [w, 0], [0, 0]], np.float32) - 0.5  # pixel centers
    homography = cv2.getPerspectiveTransform(art_px, img_px.reshape(-1, 2).astype(np.float32))
    image = cv2.warpPerspective(
        _art(), homography, SIZE, flags=cv2.INTER_CUBIC, borderValue=(200, 190, 180)
    )
    path = folder / "part.png"
    cv2.imwrite(str(path), image)
    return path


@pytest.fixture(scope="module")
def rect(photo: Path) -> Rectification:
    """The synthetic photo rectified onto the paper, at the given focal length."""
    return rectify(photo, photo.parent, BOARD, px_per_mm=10, focal_px=FOCAL)


def test_rectify_recovers_the_camera(rect: Rectification) -> None:
    assert rect.corners > 100
    assert rect.rms_px < 0.3
    assert np.allclose(rect.camera_center, CAMERA, atol=0.5)
    assert rect.focal["fit"] == pytest.approx(FOCAL, rel=0.01)
    camera_axis = CAMERA - np.array([*HOLE, 0])  # the camera looks roughly at the hole
    assert 5 < rect.tilt_deg < 25 and np.linalg.norm(camera_axis) > 400


def test_sidecar_round_trips(photo: Path, rect: Rectification) -> None:
    again = Rectification.load(photo.parent / "part.rect.json")
    assert again == rect
    assert (photo.parent / again.source).resolve() == photo.resolve()


def test_holes_and_edges_measure_in_mm(photo: Path, rect: Rectification) -> None:
    image = cv2.imread(str(photo.parent / rect.image))
    scale = Scale(rect)
    found = holes(image, scale, (44, 59, 61, 76), 4, 11)
    by_size = sorted(found, key=lambda h: h.diameter)
    assert len(by_size) >= 2  # the hole and the ring around it
    hole, ring = by_size[0], by_size[1]
    assert (hole.hole, hole.ring, ring.hole, ring.ring) == (1, 1, 1, 2)  # one hole, two rings
    assert (hole.x, hole.y) == pytest.approx(HOLE, abs=0.03)
    assert hole.diameter == pytest.approx(HOLE_D, abs=0.05)
    assert hole.minor == pytest.approx(HOLE_D, abs=0.05)
    assert ring.diameter == pytest.approx(RING_D, abs=0.05)
    found_edges = edges(image, scale, (46, HOLE[1]), (59, HOLE[1]), count=4)
    xs = [e.x for e in found_edges]
    inner = sorted(xs, key=lambda x: abs(abs(x - HOLE[0]) - HOLE_D / 2))[:2]
    assert max(inner) - min(inner) == pytest.approx(HOLE_D, abs=0.05)


def test_edges_first_and_polarity(rect: Rectification, photo: Path) -> None:
    image = cv2.imread(str(photo.parent / rect.image))
    line = ((35, HOLE[1]), (HOLE[0], HOLE[1]))  # from outside the plate to the hole's center
    every = edges(image, Scale(rect), *line, count=10)
    first = edges(image, Scale(rect), *line, count=1, first=True)
    # the plate's edge, before anything else (OpenCV draws filled rectangles half a pixel wide)
    assert first[0].x == pytest.approx(40, abs=0.1)
    assert first[0].position == min(e.position for e in every)
    falling = edges(image, Scale(rect), *line, count=10, polarity="falling")
    assert falling and all(not e.rising for e in falling)
    with pytest.raises(ValueError):
        edges(image, Scale(rect), *line, polarity="up")


def test_parallax_correction_round_trips(rect: Rectification) -> None:
    truth = np.array([[60.0, 70.0, 8.0], [20.0, 200.0, 25.0]])
    seen = rect.project(truth)
    assert np.allclose(rect.to_plane(seen, 8.0)[0], truth[0, :2], atol=1e-6)
    on_paper = rect.to_plane(seen, 0.0)  # where the rectified image shows them
    assert not np.allclose(on_paper[0], truth[0, :2], atol=0.5)  # visibly shifted
    assert np.allclose(rect.at_height(on_paper[:1], 8.0)[0], truth[0, :2], atol=1e-6)


def test_triangulate_finds_the_height(rect: Rectification) -> None:
    from dataclasses import replace

    from cadder.photo.target import triangulate

    truth = np.array([[60.0, 70.0, 8.0]])
    # a second camera, 60 mm to the side: same intrinsics, pose from moving the center
    _, rvec, _ = _pose()
    r, _ = cv2.Rodrigues(rvec)
    other_center = _to_cv(BOARD, (CAMERA + np.array([60.0, -20.0, 0.0]))[None, :])[0]
    other = replace(rect, rvec=rect.rvec, tvec=(-r @ other_center).tolist())
    views = [(v, v.to_plane(v.project(truth), 0.0)[0]) for v in (rect, other)]
    point, miss = triangulate(views)
    assert np.allclose(point, truth[0], atol=1e-6)
    assert miss < 1e-6


def _render(path: Path, center: np.ndarray, angles: tuple[float, float, float]) -> Path:
    """The board art seen by the synthetic camera from ``center``, rotated by ``angles``."""
    k = np.array([[FOCAL, 0, SIZE[0] / 2], [0, FOCAL, SIZE[1] / 2], [0, 0, 1]])
    r, _ = cv2.Rodrigues(np.radians(np.array(angles)))
    rvec, _ = cv2.Rodrigues(r)
    tvec = -r @ _to_cv(BOARD, center[None, :])[0]
    corners = np.array(
        [[0, 0, 0], [BOARD.width, 0, 0], [BOARD.width, BOARD.height, 0], [0, BOARD.height, 0]]
    )
    img_px, _ = cv2.projectPoints(_to_cv(BOARD, corners), rvec, tvec, k, np.zeros(5))
    w, h = BOARD.width * PPM, BOARD.height * PPM
    art_px = np.array([[0, h], [w, h], [w, 0], [0, 0]], np.float32) - 0.5
    homography = cv2.getPerspectiveTransform(art_px, img_px.reshape(-1, 2).astype(np.float32))
    image = cv2.warpPerspective(_art(), homography, SIZE, flags=cv2.INTER_CUBIC)
    cv2.imwrite(str(path), image)
    return path


def test_calibrate_from_several_views(tmp_path: Path) -> None:
    from cadder.photo.target import Camera, calibrate

    views = [
        _render(tmp_path / "a.png", CAMERA, (12, -5, 0)),
        _render(tmp_path / "b.png", CAMERA + np.array([60.0, -40.0, -60.0]), (25, 10, 0.3)),
        _render(tmp_path / "c.png", CAMERA + np.array([-50.0, 30.0, -40.0]), (-15, 18, -0.2)),
    ]
    cam = calibrate(views, BOARD)
    assert cam.camera_matrix[0][0] == pytest.approx(FOCAL, rel=0.005)
    assert cam.rms_px < 0.3
    assert [v["photo"] for v in cam.views] == ["a.png", "b.png", "c.png"]
    (tmp_path / "cam.json").write_text(cam.to_json())
    again = Camera.load(tmp_path / "cam.json")
    rect = rectify(views[1], tmp_path, BOARD, px_per_mm=5, camera=again)
    assert rect.focal["source"] == "camera"
    assert np.allclose(rect.camera_center, CAMERA + np.array([60.0, -40.0, -60.0]), atol=1.0)


def test_outline_fits_a_rotated_board_despite_an_overhang() -> None:
    from cadder.photo.measure import outline

    image = np.full((900, 1200, 3), 235, np.uint8)  # pixel mode: 1 unit = 1 px
    center, size, angle = (600.0, 450.0), (500.0, 380.0), 7.0
    corners = cv2.boxPoints((center, size, angle))
    cv2.fillPoly(image, [np.round(corners * 16).astype(np.int32)], (25, 25, 25), cv2.LINE_AA, 4)
    # a component hanging over one long side, and print on the board
    cv2.rectangle(image, (480, 180), (700, 300), (30, 30, 30), -1)
    cv2.putText(image, "11 22", (450, 500), cv2.FONT_HERSHEY_SIMPLEX, 3, (230, 230, 230), 6)
    o, used = outline(image, Scale(), (0, 0, 1200, 900), avoid=[(470, 170, 710, 310)])
    assert (o.x, o.y) == pytest.approx(center, abs=1.0)
    assert (o.length, o.width) == pytest.approx(size, abs=1.5)
    assert abs(o.angle_deg) == pytest.approx(angle, abs=0.3)  # y down in pixel mode
    assert o.rms < 0.5 and all(n >= 3 for n in o.points.values())
    assert set(used) == {"+a", "-a", "+b", "-b"}


def test_height_scan_finds_a_raised_face(tmp_path: Path) -> None:
    from cadder.photo.stereo import height_scan

    rng = np.random.default_rng(1)
    texture = cv2.GaussianBlur(rng.integers(0, 255, (300, 300)).astype(np.uint8), (0, 0), 2)
    texture = cv2.cvtColor(texture, cv2.COLOR_GRAY2BGR)
    lift, face = 6.0, (60.0, 90.0, 90.0, 120.0)  # a textured square 6 mm above the paper
    views = []
    for name, center, angles in (
        ("a", CAMERA, (12, -5, 0)),
        ("b", CAMERA + np.array([70.0, -30.0, -80.0]), (25, 12, 0.2)),
        ("c", CAMERA + np.array([-50.0, 10.0, -60.0]), (6, -12, -0.05)),
    ):
        path = _render(tmp_path / f"{name}.png", center, angles)
        k = np.array([[FOCAL, 0, SIZE[0] / 2], [0, FOCAL, SIZE[1] / 2], [0, 0, 1]])
        r, _ = cv2.Rodrigues(np.radians(np.array(angles)))
        rvec, _ = cv2.Rodrigues(r)
        tvec = -r @ _to_cv(BOARD, center[None, :])[0]
        x0, y0, x1, y1 = face
        quad = np.array([[x0, y1, lift], [x1, y1, lift], [x1, y0, lift], [x0, y0, lift]])
        px, _ = cv2.projectPoints(_to_cv(BOARD, quad), rvec, tvec, k, np.zeros(5))
        h = cv2.getPerspectiveTransform(
            np.array([[0, 0], [300, 0], [300, 300], [0, 300]], np.float32) - 0.5,
            px.reshape(-1, 2).astype(np.float32),
        )
        photo = cv2.imread(str(path))
        warped = cv2.warpPerspective(texture, h, SIZE)
        mask = cv2.warpPerspective(np.full((300, 300), 255, np.uint8), h, SIZE) > 0
        photo[mask] = warped[mask]
        cv2.imwrite(str(path), photo)
        views.append((rectify(path, tmp_path, BOARD, px_per_mm=4, focal_px=FOCAL), tmp_path))
    result = height_scan(views[0], views[1:], (66, 96, 84, 114), (0, 12), 0.5, px_per_mm=12)
    assert result.z == pytest.approx(lift, abs=0.15)
    assert all(v.z is not None and v.score >= 0.5 for v in result.views), result.views


def test_overlay_on_another_photo_cropped(photo: Path, rect: Rectification) -> None:
    from cadder.photo.features import FeatureFile

    ff = FeatureFile(
        path=photo.parent / "f.json",
        features=[
            {"name": "hole", "kind": "circle", "center": [*HOLE, 0], "d": 6, "source": "photo"}
        ],
        rect=None,
        image=photo,
    )
    image, legend = overlay(ff, labels="numbers", rect=photo.parent / "part.rect.json", crop=5)
    assert legend == ["1 hole"]
    assert max(image.shape[:2]) < 300  # cropped to the hole plus 5 mm (photo ~7.9 px/mm)


def test_measured_square_scales_the_board() -> None:
    board = with_square(BOARD, 14.85)
    assert board.square_mm == 14.85
    assert board.marker_mm == pytest.approx(11 * 14.85 / 15)
    assert with_square(BOARD, None) is BOARD


def test_target_pdf_and_its_board_is_detected(tmp_path: Path) -> None:
    pdf = make_target(tmp_path / "t.pdf")
    assert pdf.read_bytes()[:4] == b"%PDF"
    page = cv2.cvtColor(target_page(BOARD, px_per_mm=8), cv2.COLOR_GRAY2BGR)
    obj, _ = detect(page, BOARD)
    fx0, fy0, fx1, fy1 = BOARD.field_mm or (0, 0, 0, 0)
    inside = (obj[:, 0] > fx0) & (obj[:, 0] < fx1) & (obj[:, 1] > fy0) & (obj[:, 1] < fy1)
    assert not inside.any()  # the white field has no corners
    assert len(obj) > 80  # but the frame around it has plenty
    assert obj[:, 2].max() == 0  # on the paper
    assert obj[:, 0].min() >= 0 and obj[:, 0].max() <= BOARD.width


def test_crop_has_the_requested_size(photo: Path, rect: Rectification) -> None:
    image = cv2.imread(str(photo.parent / rect.image))
    out = crop(image, Scale(rect), (40, 55, 70, 80), max_side=700)
    assert max(out.shape[:2]) == 700


def test_exif_focal_length(tmp_path: Path) -> None:
    from PIL import Image

    image = Image.new("RGB", (400, 300))
    exif = Image.Exif()
    exif[271] = "maker"
    sub = exif.get_ifd(0x8769)
    sub[41989] = 23
    sub[41988] = 2.0
    image.save(tmp_path / "e.jpg", exif=exif)
    i = info(tmp_path / "e.jpg")
    assert (i.width, i.height, i.make, i.focal_35mm, i.digital_zoom) == (400, 300, "maker", 23, 2)
    assert i.focal_px == pytest.approx(23 * 2 * 500 / math.hypot(36, 24))


def test_feature_file_overlay_and_table(photo: Path, rect: Rectification) -> None:
    path = photo.parent / "features.json"
    path.write_text(
        json.dumps(
            {
                "rectification": "part.rect.json",
                "frame": {"origin": list(HOLE), "angle_deg": 90},
                "features": [
                    {
                        "name": "hole",
                        "kind": "circle",
                        "center": [0, 0, 0],
                        "d": 6,
                        "source": "photo",
                        "band": 0.05,
                    },
                    {
                        "name": "plate",
                        "kind": "box",
                        "center": [0, 0, 1],
                        "size": [25, 30, 2],
                        "source": "measured",
                    },
                    {
                        "name": "edge",
                        "kind": "line",
                        "points": [[0, 0], [5, 0]],
                        "source": "assumed",
                    },
                    {"name": "bad", "kind": "blob"},
                ],
            }
        )
    )
    ff = read(path)
    assert any("bad" in e for e in ff.errors)
    assert np.allclose(ff.to_target(np.array([[1.0, 0, 0]]))[0], [HOLE[0], HOLE[1] + 1, 0])
    for on in ("photo", "rectified"):
        assert overlay(ff, on)[0].ndim == 3
    text = table(ff)
    assert "| hole | circle | (0, 0, 0) | Ø6 | photo | 0.05 |" in text
