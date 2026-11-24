"""``cadder photo``: command-line tools for measuring parts from photos (docs/photo.md).

Every command prints plain text (or JSON with ``--json``) and writes images next to its input
unless ``--out`` says otherwise. Coordinates are millimeters in the target frame for a
rectified image (``*.rect.png`` with its ``.rect.json``), else image pixels.
"""

import functools
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from cadder.photo.measure import Scale

app = typer.Typer(
    name="photo",
    help="Measure parts from photos: target, rectify, crop, edges, holes, point, overlay.",
    no_args_is_help=True,
    add_completion=False,
)

Json = Annotated[bool, typer.Option("--json", help="Print JSON.")]


def plain_errors[**P, R](command: Callable[P, R]) -> Callable[P, R]:
    """Report bad input (no target found, a box outside the image, a missing file) as one
    line and exit 1, instead of a traceback."""

    @functools.wraps(command)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return command(*args, **kwargs)
        except (ValueError, FileNotFoundError, KeyError) as exc:
            typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from exc

    return wrapper


Box = tuple[float, float, float, float]


def _scale(image: Path) -> Scale:
    from cadder.photo.measure import Scale
    from cadder.photo.target import Rectification, sidecar_for

    sidecar = sidecar_for(image)
    return Scale(Rectification.load(sidecar) if sidecar else None)


def _echo_json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


@app.command("info")
@plain_errors
def info_command(photos: list[Path], as_json: Json = False) -> None:
    """Size and camera data (EXIF focal length, zoom, focal length in pixels) of photos."""
    from cadder.photo.image import info

    rows = []
    for p in photos:
        i = info(p)
        rows.append({**asdict(i), "path": str(p), "focal_px": i.focal_px})
    if as_json:
        _echo_json(rows)
        return
    for r in rows:
        f = r["focal_px"]
        typer.echo(
            f"{r['path']}: {r['width']}×{r['height']}, {r['make'] or '?'} {r['model'] or ''}, "
            f"focal {r['focal_mm'] or '?'} mm (35 mm eq. {r['focal_35mm'] or '?'}, "
            f"zoom {r['digital_zoom'] or 1:g}) → {f'{f:.0f} px' if f else 'unknown'}"
        )


@app.command("convert")
@plain_errors
def convert_command(
    photos: list[Path],
    out: Annotated[Path | None, typer.Option(help="Output folder (default: next to each).")] = None,
) -> None:
    """Convert photos (e.g. HEIC) to upright JPEGs, keeping EXIF."""
    from cadder.photo.image import to_jpeg

    for p in photos:
        target = (out or p.parent) / (p.stem + ".jpg")
        if target.resolve() == p.resolve():
            typer.echo(f"{p}: already a JPEG")
            continue
        typer.echo(f"wrote {to_jpeg(p, target)}")


@app.command("target")
@plain_errors
def target_command(
    out: Annotated[Path, typer.Argument(help="PDF to write.")] = Path("charuco-target.pdf"),
    squares: Annotated[str, typer.Option(help="Squares along x and y, e.g. 12x17.")] = "12x17",
    square: Annotated[float, typer.Option(help="Square size, mm.")] = 15.0,
    marker: Annotated[float, typer.Option(help="Marker size, mm.")] = 11.0,
    paper: Annotated[str, typer.Option(help="A4, LETTER or A3.")] = "A4",
    field: Annotated[
        str, typer.Option(help="White field for the part: squares x0,y0,x1,y1, or 'none'.")
    ] = "3,4,9,13",
) -> None:
    """Write a printable ChArUco target (print at 100 %, then measure 10 squares).

    By default the middle is a plain white field for the part (a dark part's edges vanish
    over black squares); the corners around it are enough to rectify.
    """
    from cadder.photo.target import Board, make_target

    sx, sy = (int(v) for v in squares.lower().split("x"))
    blank = None
    if field.lower() != "none":
        a, b, c, d = (int(v) for v in field.split(","))
        blank = (a, b, c, d)
    board = Board(sx, sy, square, marker, field=blank)
    typer.echo(f"wrote {make_target(out, board, paper)}: {board.label()}")


@app.command("rectify")
@plain_errors
def rectify_command(
    photo: Path,
    square: Annotated[
        float | None, typer.Option(help="Printed square size as measured, mm (default: nominal).")
    ] = None,
    squares: Annotated[str, typer.Option(help="Board squares, e.g. 12x17.")] = "12x17",
    nominal_square: Annotated[float, typer.Option(help="Board's nominal square, mm.")] = 15.0,
    nominal_marker: Annotated[float, typer.Option(help="Board's nominal marker, mm.")] = 11.0,
    height: Annotated[
        float, typer.Option(help="Rectify the plane this far above the paper, mm.")
    ] = 0.0,
    region: Annotated[
        str | None, typer.Option(help="x0,y0,x1,y1 in target mm (default: whole board).")
    ] = None,
    ppmm: Annotated[float | None, typer.Option(help="Output pixels per mm.")] = None,
    focal: Annotated[float | None, typer.Option(help="Focal length in pixels.")] = None,
    camera: Annotated[
        Path | None, typer.Option(help="A camera file from `calibrate` (same phone and zoom).")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Output folder (default: photo's).")] = None,
) -> None:
    """Find the target, solve the camera pose and write a square-on image in mm (+ sidecar).

    Writes PHOTO.rect.png and PHOTO.rect.json, or PHOTO.h<H>.rect.* with --height H.
    With --region, the pose comes from the target corners nearest the region (curled paper).
    """
    from cadder.photo.target import Board, rectify, summary, with_square

    sx, sy = (int(v) for v in squares.lower().split("x"))
    board = with_square(Board(sx, sy, nominal_square, nominal_marker), square)
    box: tuple[float, float, float, float] | None = None
    if region:
        x0, y0, x1, y1 = (float(v) for v in region.split(","))
        box = (x0, y0, x1, y1)
    from cadder.photo.target import Camera

    cam = Camera.load(camera) if camera else None
    rect = rectify(photo, out or photo.parent, board, height, box, ppmm, focal, cam)
    typer.echo(summary(rect))


@app.command("calibrate")
@plain_errors
def calibrate_command(
    photos: list[Path],
    square: Annotated[
        float | None, typer.Option(help="Printed square size as measured, mm (default: nominal).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Camera file to write.")] = Path("camera.json"),
) -> None:
    """Calibrate the camera from several photos of the target taken at the same zoom.

    Views from different angles pin down the focal length and lens distortion; use the
    result with `rectify --camera`. Phones change lens and focal length with the zoom: one
    camera file per zoom setting.
    """
    from cadder.photo.target import DEFAULT_BOARD, calibrate, with_square

    cam = calibrate(photos, with_square(DEFAULT_BOARD, square))
    out.write_text(cam.to_json())
    k = cam.camera_matrix
    typer.echo(
        f"wrote {out}: focal {k[0][0]:.0f} px, center ({k[0][2]:.0f}, {k[1][2]:.0f}), "
        f"k1 {cam.dist[0]:.4f}, k2 {cam.dist[1]:.4f}; reprojection {cam.rms_px:.2f} px"
    )
    for v in cam.views:
        typer.echo(f"  {v['photo']}: {v['corners']} corners, {v['rms_px']:.2f} px")


@app.command("crop")
@plain_errors
def crop_command(
    image: Path,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    grid: Annotated[float | None, typer.Option(help="Grid step (mm or px).")] = None,
    size: Annotated[int, typer.Option(help="Longest side of the output, px.")] = 1400,
    out: Annotated[Path | None, typer.Option(help="Output image.")] = None,
) -> None:
    """An enlarged crop with a labeled grid, for finding points by eye (mm on rectified images)."""
    from cadder.photo.image import load, save
    from cadder.photo.measure import crop

    scale = _scale(image)
    result = crop(load(image), scale, (x0, y0, x1, y1), grid, size)
    target = out or image.parent / "crops" / f"{image.stem}_{x0:g}_{y0:g}_{x1:g}_{y1:g}.png"
    typer.echo(f"wrote {save(result, target)} ({scale.unit})")


@app.command("edges")
@plain_errors
def edges_command(
    image: Path,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    band: Annotated[float, typer.Option(help="Width averaged across the line, px.")] = 5,
    count: Annotated[int, typer.Option(help="Edges to report.")] = 6,
    first: Annotated[
        bool, typer.Option("--first", help="The first edges from the start, not the strongest.")
    ] = False,
    polarity: Annotated[
        str | None, typer.Option(help="Only 'rising' (dark→light) or 'falling' edges.")
    ] = None,
    min_strength: Annotated[
        float, typer.Option("--min-strength", help="Weakest edge kept (gray levels / px).")
    ] = 8,
    as_json: Json = False,
) -> None:
    """Edges along the line (x0, y0) → (x1, y1), to sub-pixel (mm on rectified images).

    To place an object's outer edge, start the line outside it and use --first (with
    --polarity), so print or texture inside the object doesn't win.
    """
    from cadder.photo.image import load
    from cadder.photo.measure import edges

    scale = _scale(image)
    found = edges(
        load(image), scale, (x0, y0), (x1, y1), band, count, min_strength, first, polarity
    )
    if as_json:
        _echo_json([asdict(e) for e in found])
        return
    for e in found:
        kind = "dark→light" if e.rising else "light→dark"
        typer.echo(
            f"at {e.position:8.3f} {scale.unit}: ({e.x:.3f}, {e.y:.3f}) {kind}, "
            f"strength {e.strength:.0f}"
        )


@app.command("holes")
@plain_errors
def holes_command(
    image: Path,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    d_min: Annotated[float, typer.Option("--dmin", help="Smallest diameter (mm or px).")] = 1,
    d_max: Annotated[float, typer.Option("--dmax", help="Largest diameter (mm or px).")] = 10,
    count: Annotated[int, typer.Option(help="Most holes to report (each with all its rings).")] = 4,
    as_json: Json = False,
) -> None:
    """Round features in the box (holes, pads, screw heads): center, diameters, fit RMS.

    A hole's concentric edges (wall, plating, mask ring) are listed as its rings, inside out.
    """
    from cadder.photo.image import load
    from cadder.photo.measure import holes

    scale = _scale(image)
    found = holes(load(image), scale, (x0, y0, x1, y1), d_min, d_max, count)
    if as_json:
        _echo_json([asdict(h) for h in found])
        return
    if not found:
        typer.echo("no circles found")
    for h in found:
        typer.echo(
            f"hole {h.hole} ring {h.ring}: center ({h.x:.3f}, {h.y:.3f}) Ø{h.diameter:.3f} "
            f"{scale.unit} (minor {h.minor:.3f}, axis {h.angle_deg:.0f}°), "
            f"fit RMS {h.rms:.3f}, {h.points}/120 rays"
        )


@app.command("point")
@plain_errors
def point_command(
    sidecar: Annotated[Path, typer.Argument(help="A rectification's .rect.json.")],
    u: float,
    v: float,
    height: Annotated[float, typer.Option(help="The feature's height above the paper, mm.")] = 0,
    from_photo: Annotated[
        bool, typer.Option("--photo", help="U V are photo pixels (default: rectified mm).")
    ] = False,
) -> None:
    """Where a feature really is (target mm), given where it is seen and its height.

    Parallax: a feature above the rectified plane appears shifted away from the camera.
    """
    import numpy as np

    from cadder.photo.target import Rectification

    rect = Rectification.load(sidecar)
    point = np.array([[u, v]], dtype=np.float64)
    xy = rect.to_plane(point, height) if from_photo else rect.at_height(point, height)
    typer.echo(f"({xy[0, 0]:.3f}, {xy[0, 1]:.3f}) mm at z = {height:g}")


@app.command("triangulate")
@plain_errors
def triangulate_command(
    views: Annotated[
        list[str],
        typer.Argument(help="Two or more SIDECAR:X,Y (the feature on each rectified plane, mm)."),
    ],
) -> None:
    """A feature's height from two or more photos taken from different places.

    Give where the same feature (a corner, a hole center, a screw head) appears on each
    photo's rectified image; prints its x, y, z (target mm) and how well the rays meet.
    """
    import numpy as np

    from cadder.photo.target import Rectification, triangulate

    parsed = []
    for v in views:
        path, _, xy = v.rpartition(":")
        x, y = (float(c) for c in xy.split(","))
        parsed.append((Rectification.load(Path(path)), np.array([x, y])))
    if len(parsed) < 2:
        raise ValueError("give the feature in at least two photos")
    point, miss = triangulate(parsed)
    typer.echo(
        f"({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) mm; rays meet within {miss:.3f} mm RMS"
    )


@app.command("overlay")
@plain_errors
def overlay_command(
    features: Path,
    on: Annotated[str, typer.Option(help="photo or rectified.")] = "photo",
    rect: Annotated[
        Path | None,
        typer.Option(help="Draw on this photo's rectification instead (another photo of the set)."),
    ] = None,
    crop: Annotated[
        float | None, typer.Option(help="Crop to the features plus this margin (mm).")
    ] = None,
    labels: Annotated[str, typer.Option(help="names, numbers (with a legend) or none.")] = "names",
    out: Annotated[Path | None, typer.Option(help="Output image.")] = None,
) -> None:
    """Draw a feature file onto a photo (colors by source) to check it by eye."""
    from cadder.photo.features import overlay, read
    from cadder.photo.image import save

    ff = read(features)
    for e in ff.errors:
        typer.secho(f"warning: {e}", fg=typer.colors.YELLOW, err=True)
    image, legend = overlay(ff, on, labels, rect, crop)
    which = f"_{rect.name.split('.')[0]}" if rect else ""
    target = out or features.parent / "overlays" / f"{features.stem}{which}_{on}.jpg"
    typer.echo(f"wrote {save(image, target)}")
    if labels == "numbers":
        typer.echo("\n".join(legend))


@app.command("height")
@plain_errors
def height_command(
    reference: Annotated[Path, typer.Argument(help="The reference photo's .rect.json.")],
    others: Annotated[list[Path], typer.Argument(help="Other photos' .rect.json (same set).")],
    box: Annotated[str, typer.Option(help="x0,y0,x1,y1 (target mm): a flat, textured patch.")],
    zmin: Annotated[float, typer.Option(help="Lowest height tried, mm.")] = 0.0,
    zmax: Annotated[float, typer.Option(help="Highest height tried, mm.")] = 20.0,
    step: Annotated[float, typer.Option(help="Height step, mm.")] = 0.25,
    search: Annotated[float, typer.Option(help="How far a match may shift, mm.")] = 2.0,
    curve: Annotated[bool, typer.Option("--curve", help="Print the sweep.")] = False,
    as_json: Json = False,
) -> None:
    """The height of a flat face above the paper, from several photos (a plane sweep).

    Put the box on print or texture that lies on one face (silkscreen on a PCB, a label);
    the photos must show the part unmoved. Each other photo gives a height where its view of
    the patch stops shifting against the reference; they are combined by how much parallax
    each sees.
    """
    from cadder.photo.stereo import height_scan
    from cadder.photo.target import Rectification

    x0, y0, x1, y1 = (float(v) for v in box.split(","))
    ref = (Rectification.load(reference), reference.parent)
    views = [(Rectification.load(o), o.parent) for o in others]
    result = height_scan(ref, views, (x0, y0, x1, y1), (zmin, zmax), step, search)
    if as_json:
        _echo_json(asdict(result))
        return
    if result.z is None:
        typer.echo("no height: no photo matched the patch well (move the box onto texture)")
    else:
        typer.echo(f"height {result.z:.2f} mm above the paper (spread {result.spread:.2f} mm)")
    for v in result.views:
        z = "-" if v.z is None else f"{v.z:.2f}"
        typer.echo(
            f"  {v.photo}: z {z}, match {v.score:.2f}, parallax {v.sensitivity:.2f} mm/mm"
            + ("" if v.score >= 0.5 else " (weak match: not used)")
        )
    if curve:
        for zz, sc, dx, dy in result.curve:
            typer.echo(f"  z {zz:6.2f}: match {sc:.2f}, shift ({dx:+.2f}, {dy:+.2f})")


@app.command("outline")
@plain_errors
def outline_command(
    image: Path,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    light: Annotated[
        bool, typer.Option("--light", help="A light part on a dark background.")
    ] = False,
    guess: Annotated[
        str | None, typer.Option(help="x,y,length,width,angle: skip the threshold first guess.")
    ] = None,
    avoid: Annotated[
        list[str] | None,
        typer.Option(help="x0,y0,x1,y1: no measuring lines here (overhanging parts); repeatable."),
    ] = None,
    lines: Annotated[int, typer.Option(help="Measuring lines per side.")] = 16,
    span: Annotated[float, typer.Option(help="Share of each side measured (corners left).")] = 0.7,
    out: Annotated[Path | None, typer.Option(help="Check image (default: crops/).")] = None,
    as_json: Json = False,
) -> None:
    """Fit a rotated rectangle to a part's outline (a board, a plate) in the box.

    Prints the center, length, width and angle (the part frame for a feature file), the fit's
    RMS and the edge points used per side, and writes a crop with them drawn to check.
    """
    import numpy as np

    from cadder.photo.image import load, save
    from cadder.photo.measure import crop, outline

    scale = _scale(image)
    g = tuple(float(v) for v in guess.split(",")) if guess else None
    av = [tuple(float(v) for v in a.split(",")) for a in avoid or []]
    img = load(image)
    o, used = outline(
        img, scale, (x0, y0, x1, y1), not light, lines, guess=g, avoid=av, span=span,  # type: ignore[arg-type]
    )  # fmt: skip
    if as_json:
        _echo_json({**asdict(o), "edge_points": used})
    else:
        typer.echo(
            f"center ({o.x:.3f}, {o.y:.3f}) {scale.unit}, length {o.length:.3f} x width "
            f"{o.width:.3f}, angle {o.angle_deg:.2f}°, fit RMS {o.rms:.3f}; "
            f"edge points per side {o.points}"
        )
    import cv2

    marked = img.copy()
    k = scale.px_per_unit
    corners = scale.to_px(np.array(o.corners)).round().astype(np.int32)
    cv2.polylines(marked, [corners], True, (0, 0, 255), max(1, round(k / 20)), cv2.LINE_AA)
    for pts in used.values():
        for q in scale.to_px(np.array(pts)) if pts else []:
            cv2.circle(marked, (round(q[0]), round(q[1])), max(2, round(k / 10)), (0, 200, 0), -1)
    view = crop(marked, scale, (x0, y0, x1, y1))
    target = out or image.parent / "crops" / f"{image.stem}_outline.png"
    typer.echo(f"wrote {save(view, target)}")


@app.command("table")
@plain_errors
def table_command(features: Path) -> None:
    """Print a feature file as a Markdown table (for the report)."""
    from cadder.photo.features import read, table

    ff = read(features)
    for e in ff.errors:
        typer.secho(f"warning: {e}", fg=typer.colors.YELLOW, err=True)
    typer.echo(table(ff))


def main() -> None:
    """Entry point of ``python -m cadder.photo`` (no project needed)."""
    app()
