# Measuring parts from photos: `cadder photo`

Tools for turning photos of a physical part into dimensions: a printed calibration target,
rectification onto it, measuring in millimeters, and a feature file that is drawn back onto
the photo to check it. Module: `cadder.photo`. Needs the `photo` extra (OpenCV, Pillow,
pillow-heif): `uv sync --extra photo`. Run as `cadder photo COMMAND` (in a project) or
`python -m cadder.photo COMMAND` (anywhere).

## Workflow

1. **Print the target once:** `cadder photo target` writes `charuco-target.pdf` (A4, 12 × 17
   squares of 15 mm, with a plain white field in the middle, x 45–135, y 60–195 mm: a dark
   part's edges vanish over black squares; `--field none` for a full board). Print at 100 % ("actual size", no fit to page) on plain paper, lay it flat
   (tape it down at the edges on a rigid, flat surface: a curl of 1 mm shows up as ~0.1–0.3 mm
   of error), and **measure 10 squares** with a caliper: printers scale by up to
   ~1 %. Use that value as `--square` (e.g. 10 squares = 149.2 mm → `--square 14.92`).
2. **Photograph the part lying in the white field:** one face per photo, the target's
   corners around the field visible (about 20 corners are plenty), sharp,
   evenly lit, no glare on the target. Step back and zoom in (2–3×) to reduce perspective.
   A slight angle is fine: it is solved for. **Don't touch the part between photos** of one
   set: `triangulate` needs it in the same place in every photo.
3. **Calibrate (for a set of photos):** `cadder photo calibrate PHOTOS... --square 14.92
   --out camera.json` fits the focal length, principal point and lens distortion from all
   photos taken at the same zoom (more angles, better). Phone EXIF focal lengths at digital
   zoom were off by ~6 % in practice. Pass `--camera camera.json` to every `rectify`.
4. **Rectify:** `cadder photo rectify PHOTO --square 14.92` finds the target, solves the
   camera's pose and writes `PHOTO.rect.png` (square-on, target millimeters, y up) and its
   sidecar `PHOTO.rect.json`. Check the summary: target corners, reprojection error (should be
   under 1 px), the focal length from EXIF vs fitted to the target, the camera's tilt.
   For a face above the paper (a PCB's top, a PSU's lid), add `--height H` (mm): that plane
   becomes the rectified one, so its features measure true. With `--region x0,y0,x1,y1` the
   pose comes only from the target corners nearest that region (a margin of 2 squares,
   widened up to 6 until there are 20 corners, as around the white field): paper is rarely
   flat, and the nearby corners describe the paper under the part best. Rectifying at a
   height writes `PHOTO.h<H>.rect.png` / `.json`, so several heights sit side by side.
   The reported reprojection error, in mm, is a floor for every measurement on that photo.
5. **Measure** on the rectified image, in target millimeters:
   - `crop IMG X0 Y0 X1 Y1 [--grid STEP]`: an enlarged region with a labeled grid, to look at.
   - `edges IMG X0 Y0 X1 Y1`: sub-pixel edges along the line from (X0, Y0) to (X1, Y1),
     with direction (dark→light or light→dark) and strength; by default the strongest. To
     place a part's outer edge, start the line outside the part and add `--first` (the first
     edges from the start) and `--polarity rising|falling`, so print or texture on the part
     doesn't win; `--min-strength` drops faint ones.
   - `holes IMG X0 Y0 X1 Y1 --dmin D --dmax D`: circles in the box (holes, pads, screw heads)
     as ellipses: center, major/minor diameter, fit RMS and how many of 120 rays found the
     edge. A hole's concentric edges (its wall, a plating or mask ring) are listed as its
     rings, numbered from the inside out (`hole 1 ring 1` is the innermost edge of the
     best-supported hole), so the same edge has the same label in every photo.
   - `point SIDECAR U V --height H`: where a feature seen at (U, V) on the rectified plane
     really is if it is at height H (parallax); `--photo` for a photo pixel instead.
   - `triangulate A.rect.json:X,Y B.rect.json:X,Y`: a feature's x, y and **height** from two
     (or more) photos taken from different places (the further apart, the better), given
     where it appears on each rectified image; also how closely the camera rays meet.
6. **Record** the features in a feature file and **check** it: `overlay FEATURES.json`
   (on the photo, or `--on rectified`) draws them, colored by source; `table FEATURES.json`
   prints the Markdown table for the report.

Without a target, `info`, `crop`, `edges`, `holes` and pixel-mode feature files still work on
the photo in pixels; the scale then has to come from something else in the picture.

## Frames

- **Target frame** (mm): origin at the board's bottom-left corner as printed (the label is
  under the board), x right, y up, z up out of the paper. Rectified images show it with
  y up = image up; their crops and measurements are in this frame.
- **Part frame:** the feature file's `frame` places it on the target: `origin` (target mm)
  and `angle_deg` (its x axis, counterclockwise from the target's x). z is height above the
  paper in both.

## Feature file

```json
{
  "rectification": "top.rect.json",
  "frame": {"origin": [62.1, 80.4], "angle_deg": 90},
  "features": [
    {"name": "PCB", "kind": "box", "center": [0, 0, 0.75], "size": [20.3, 20, 1.5],
     "source": "measured", "band": 0.1},
    {"name": "hole L", "kind": "circle", "center": [-6.9, 7.5, 1.5], "d": 3.2,
     "source": "photo", "band": 0.15, "notes": "unplated"},
    {"name": "lever", "kind": "line", "points": [[10.9, 4.2, 4], [13.9, -8.9, 4]],
     "source": "photo", "band": 0.4},
    {"name": "lever tip", "kind": "point", "center": [13.9, -8.9, 4], "source": "photo"}
  ]
}
```

Kinds: `box` (axis-aligned in the part frame: center and size), `circle` (center, `d`, drawn
in the plane `z`), `line` (polyline `points`), `point`. Every feature needs a `source`:
`measured`, `datasheet`, `photo` or `assumed` (overlay colors: green, blue, yellow,
magenta). `band` (±mm) and `notes` are optional. Without a rectification, give
`"image": "photo.jpg"`: coordinates are then that image's pixels and z is ignored.

## Accuracy

On a synthetic photo (known camera, 13° tilt), the camera pose comes back to 0.5 mm, the
fitted focal length to 0.1 %, and a 6 mm hole's center and diameter to 0.02 mm
(`cadder/tests/test_photo.py`). On real photos expect about ±0.1–0.2 mm for sharp edges on the
rectified plane, plus:

- the printed square's measurement (one caliper reading of 10 squares: ~0.05 %);
- the height of off-plane features: `point` shows how far a 1 mm height error moves them;
- soft edges (chamfers, solder mask, blur) and parts that move (springs, cables).

Phones store the main lens's 35 mm-equivalent focal length and the digital zoom separately;
`info` multiplies them. `rectify` also fits the focal length to the target and notes when the
two disagree by more than 5 %.
