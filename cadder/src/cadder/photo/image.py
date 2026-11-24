"""Loading photos (JPEG, PNG, HEIC) and reading their camera data from EXIF."""

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageOps

#: A color image as OpenCV uses it: rows × columns × BGR.
BGR = npt.NDArray[np.uint8]

#: Diagonal of a 36 × 24 mm frame, for converting 35 mm-equivalent focal lengths.
FULL_FRAME_DIAGONAL = math.hypot(36, 24)

#: EXIF tags (the Exif sub-IFD): focal length, 35 mm equivalent, digital zoom ratio.
_EXIF_IFD = 0x8769
_FOCAL_LENGTH = 37386
_FOCAL_35MM = 41989
_DIGITAL_ZOOM = 41988
_MAKE, _MODEL = 271, 272


@dataclass(frozen=True)
class PhotoInfo:
    """Size and camera data of a photo (after applying its EXIF orientation)."""

    path: Path
    width: int
    height: int
    make: str | None = None
    model: str | None = None
    focal_mm: float | None = None  #: the lens's real focal length
    focal_35mm: float | None = None  #: 35 mm-equivalent focal length of the lens
    digital_zoom: float | None = None  #: digital zoom ratio (crop), if any

    @property
    def focal_px(self) -> float | None:
        """Focal length in pixels, from the 35 mm equivalent and the digital zoom.

        Phones record the main lens's 35 mm equivalent and the zoom separately; the image is
        cropped by the zoom and scaled back to full size, so the zoom multiplies the focal
        length. An estimate: ``rectify`` also fits it from the target and reports both.
        """
        if not self.focal_35mm:
            return None
        zoom = self.digital_zoom if self.digital_zoom and self.digital_zoom > 1 else 1.0
        return self.focal_35mm * zoom * math.hypot(self.width, self.height) / FULL_FRAME_DIAGONAL


def _open(path: Path) -> Image.Image:
    """Open a photo with Pillow (HEIC too), turned upright by its EXIF orientation."""
    if path.suffix.lower() in (".heic", ".heif"):
        from pillow_heif import register_heif_opener

        register_heif_opener()
    image = Image.open(path)
    return ImageOps.exif_transpose(image)


def _number(value: object) -> float | None:
    """An EXIF number (int, float or rational) as a float; ``None`` when missing or zero."""
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except TypeError, ValueError, ZeroDivisionError:
        return None
    return number or None


def info(path: Path) -> PhotoInfo:
    """Size and camera data of the photo at ``path``."""
    with _open(path) as image:
        exif = image.getexif()
        sub = exif.get_ifd(_EXIF_IFD)
        make, model = exif.get(_MAKE), exif.get(_MODEL)
        return PhotoInfo(
            path=path,
            width=image.width,
            height=image.height,
            make=str(make).strip("\x00 ") if make else None,
            model=str(model).strip("\x00 ") if model else None,
            focal_mm=_number(sub.get(_FOCAL_LENGTH)),
            focal_35mm=_number(sub.get(_FOCAL_35MM)),
            digital_zoom=_number(sub.get(_DIGITAL_ZOOM)),
        )


def load(path: Path) -> BGR:
    """The photo at ``path`` as an upright BGR image."""
    with _open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    return np.ascontiguousarray(rgb[:, :, ::-1])


def save(image: BGR, path: Path, quality: int = 92) -> Path:
    """Write ``image`` (BGR) to ``path`` (format from the suffix); returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = Image.fromarray(np.ascontiguousarray(image[:, :, ::-1]))
    if path.suffix.lower() in (".jpg", ".jpeg"):
        rgb.save(path, quality=quality)
    else:
        rgb.save(path)
    return path


def to_jpeg(path: Path, out: Path) -> Path:
    """Convert a photo (e.g. HEIC) to an upright JPEG, keeping its EXIF data."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with _open(path) as image:
        exif = image.getexif()
        exif.pop(0x0112, None)  # orientation: already applied
        image.convert("RGB").save(out, quality=95, exif=exif.tobytes())
    return out
