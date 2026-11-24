# Measuring parts from photos

How we turn photos of a part (a PSU, a board, a motor, a bracket) into dimensions the CAD can
use, and how the **`photo-metrologist`** sub-agent (`.claude/agents/photo-metrologist.md`)
does it. Status: **phase 1** (agent and protocol, no project code; T3.29).

## 1. Why a sub-agent

- **Context.** A real job takes 5–15 photos plus overlays and re-checks. The sub-agent spends
  those tokens in its own context and returns a short spec.
- **Method.** Good numbers from photos need the same steps every time: find the scale
  reference, correct perspective, state an error band, separate what is seen from what is
  guessed. A dedicated prompt applies them every time.
- **Independence.** It describes the object; it never edits CAD, `src/` or `docs/`. The main
  session models it and records the numbers (README §7.1, §7.3).

## 2. The loop

A sub-agent cannot ask the user directly, so the main session relays:

1. The user shares the photos, usually as a **Google Drive folder link**, and says what is
   needed ("outline, mounting holes, connectors, vents"). The main session lists the folder
   (Drive connector, `search_files` with `parentId = '<folder id>'`) and downloads each image
   (`download_file_content`): the connector saves the full-resolution file under the session's
   `tool-results/` folder and gives its path. The main session copies them into
   `photos/<object>/` under their Drive names and checks the sizes match. The sub-agent has no
   Drive access; it only reads the local copies. Files the user drops into `photos/<object>/`
   directly work too.
2. The main session calls `photo-metrologist` with the folder, the question and anything
   already known (a model number, caliper readings, which face matters for the design).
3. The agent replies with either a **spec** or **NEEDS INPUT**: a short, ranked list of
   measurements or photos, each with the reason it matters.
4. The main session asks the user, then resumes **the same agent** (`SendMessage` to its id)
   with the answers, so it keeps what it has worked out. New photos go into the same Drive
   folder; the main session fetches the new ones into `photos/<object>/` first.
5. The main session copies the result into `plotzker.hardware` / `cadder.hardware` and
   `docs/hardware.md`, keeping the agent's source tags (`measured`, `photo ±x`, `datasheet`,
   `assumed`), and marks photo-only numbers *assumed* (README §7.1).

## 3. Photo protocol (for the user)

The agent may point you here when it asks for more photos.

- **One face per photo, square-on.** Hold the camera parallel to the face you want measured.
- **Step back and zoom in** (2–3× on a phone). A longer lens means less perspective, so near and
  far features keep the same scale.
- **Lay the part in the white field of the printed ChArUco target** (`cadder photo target`,
  print at 100 %, measure 10 squares once with the caliper and tell the agent), **taped flat**
  on a rigid surface: a curled sheet limited the first target photos to ~0.2 mm, and a black
  PCB over black squares lost its edges (trial 2). Keep target corners visible
  around the part. This fixes scale, perspective and the camera's angle in one photo.
  Without it: a steel ruler or the caliper jaws laid flat *on* the face being measured; a
  ruler on the table beside a part is below its top face (even a PCB resting on its solder
  joints sits ~2 mm above it), and that error scales everything.
- **Even, diffuse light;** no flash glare. Holes and vents should look dark against the face.
- **Fill the frame** with the part, leaving a margin; keep the whole face in focus.
- **Add an overview photo** (three-quarter view) so the agent can tell which face is which.
- **Take two photos of each face from different positions** (e.g. one from straight above,
  one from 5–10 cm to the side) **without touching the part in between**: the agent
  triangulates heights from them (`triangulate`).
- **Say which way is up/front** if it is not obvious, and give any caliper readings you
  already have: one or two good readings fix the scale of a whole face.

Rough accuracy to expect: on the target, about ±0.1–0.2 mm for sharp edges (more for
features well above the paper, unless their height is known); with a ruler on the face,
±0.3–0.5 mm on a 100 mm face; without a reference in plane, proportions only. Hole *spacing* is more reliable
than hole *diameter* (edges blur). Anything a part's fit depends on (hole pitch for screws,
connector clearance) should be confirmed with the caliper.

## 4. What the agent returns

A report in `photos/<object>/report.md`, and the same text as its reply:

- **Identification:** what the part is, model or datasheet if found, which photo shows which face.
- **Frame:** origin and axes, stated as for `plotzker.hardware` modules (e.g. "origin at the
  front-left-bottom corner, x right, y back, z up").
- **Outline and features** in a table: name, position, size, source tag and error band.
  Features are the ones asked for: mounting holes (thread or Ø, depth if visible),
  connectors and terminals (and the free space their plugs need), vents (zones that must stay
  open), switches, LEDs, keep-out zones.
- **Measure to confirm:** caliper checks, ranked by how much each number matters to the design.
- **Files:** overlays (`photos/<object>/overlays/`) showing the detected features on the photos.

## 5. Tools

**Phase 2 (done):** the agent uses `cadder photo` (guide: [`cadder/docs/photo.md`](../cadder/docs/photo.md);
the `photo` extra, installed by `make develop`): `target` (the printable ChArUco PDF),
`info`, `convert`, `rectify`, `crop`, `edges`, `holes`, `point`, `overlay`, `table`. Phase 1
showed where the time went: of 133 tool calls over the two trial rounds, most rebuilt the same
crop, edge, circle-fit, ruler and overlay scripts (30 scripts, 52 images), and the scale
reference (a ruler beside the part) was the largest error. The measurement is kept in
`photos/<object>/features.json`, from which the overlay and the report's table are drawn.
The project's `.claude/settings.json` allows the agent's `cadder photo` commands and writes
under `photos/`. Scripts in `work/` are only for what the tools do not cover.

Later (not built): render the CAD model from the camera pose `rectify` found and blend it
over the photo, to check a finished model against the real part.

## 6. Storage

`photos/` is a working folder and is never committed (git-ignored): the photos, the agent's
scripts, overlays and `report.md` are development material, not source. Only the facts they give
are kept, in `plotzker.hardware` / `cadder.hardware` and `docs/hardware.md`, with their source
tags. Keep the folder locally while a part is being designed, and delete it when you like.

## 7. Phase 1 trial

Benchmark: the **Creality-type endstop board**, measured with the caliper in T3.5 and T3.14
(`docs/hardware.md`, `plotzker.hardware.endstop`). The agent measures it from new photos
without being shown those numbers; we compare.

**Trial 1 (2026-11-24).** Five phone photos from Drive (top, bottom, side, end, overview), **no
ruler**. The agent was told not to read the repo's endstop records. It took about 18 min and
96 tool calls. It found the scale from the parts' datasheets (Omron D2F-size switch, JST XH
header) and corrected for parallax using the photo metadata. It returned NEEDS INPUT, asking for
three caliper readings (board size, thickness, underside protrusion) with best estimates for
everything. Its overlay sits on the real edges.

**Round 2 (same day):** the user added one top view with a steel ruler on the table beside the
board. The same agent, resumed, fitted a camera model to 36 ruler ticks (it found a ~7° tilt),
allowed for the board's top being ~2 ± 1 mm above the ruler, and re-measured (8 min).

| Dimension | Caliper (T3.5, T3.14) | Round 1 (no ruler) | Round 2 (ruler) |
|---|---|---|---|
| Board width (across the holes) | 20 (re-measured) | 19.9 ±0.4 ✓ | 19.4 ±0.3 **✗ −0.6** |
| Board length (connector → switch, PCB only) | **20.3** (re-measured; record said 19) | 20.0 ±0.4 ✓ | 19.6 ±0.3 **✗ −0.7** |
| PCB thickness | 1.5 | 1.3 ±0.3 ✓ | (not remeasured) |
| Hole pitch | 15 | 14.9 ±0.3 ✓ | 14.65 ±0.2 **✗ −0.35** |
| Hole center from the rear edge | 3.0 | 3.0 ±0.3 ✓ | 3.0 ±0.15 ✓ |
| Hole center from the side edges | 2.5 | 2.3 / 2.7 ±0.3 ✓ | 2.4 / 2.3 ±0.15 ✓ |
| Connector width × length | 10 × 7.2 | 10.2 × 7.1 ±0.4 ✓ | 10.2 × 7.1 ±0.3 ✓ |
| Connector height | 5.6 | 6.1 datasheet **✗ +0.5** | (not remeasured) |
| Connector past the rear edge | 2 | 1.9 ±0.3 ✓ | 2.0 ±0.2 ✓ |
| Switch body across × along the board | 13 × 6.3 | 13.0 × 6.75 ±0.4 (along borderline) | 13.0 × 6.3 ±0.3 ✓ |
| Switch body height | 5.3 | 5.8 datasheet **✗ +0.5** | (not remeasured) |
| Switch body past the front edge | 1.0 | 1.5 ±0.3 **✗ +0.5** | 1.1 ±0.2 ✓ |
| Lever width | 3.8 | 3.9 ±0.5 ✓ | — |
| Lever tip past the front edge at rest | 5.0 | 4.6 ±0.5 ✓ | 4.1 ±0.4 **✗ −0.9** (tip blurred; spring-loaded) |
| Lever hinge end | left (connector at rear) | left ✓ | — |
| Solder joints below the board | up to 1.8 | ~1–2, keep-out 2.0 ✓ | — |

The ruler fixed the component positions (both overhangs, the switch body), but put the board
outline ~3 % small. **Re-measured with the caliper: the PCB is 20.3 long × 20 wide.** The
recorded 19 was wrong (T3.5 had it from photos too), so round 1 was right about the outline and
about the board being nearly square, and round 2's ruler made it worse. Likely cause: the scale
at the PCB plane depends on the assumed height of the board above the ruler and on the fitted
camera distance; parts at other heights (the switch, the connector) are corrected separately
and came out right. **Final tally against the caliper:** round 1, 12 of 16 within its bands
and 1 borderline (misses: two datasheet heights of clone parts, the switch overhang); round 2,
6 of 10 remeasured (misses: board length and width, the hole pitch, the blurred lever tip).

**Trial 2 (2026-11-24), the `cadder photo` tools on the printed target.** Two photos (whole
sheet from above, and closer from another position), board resting on its solder joints, target
printed at 96.7 % (`--square 14.5`) and visibly curled. A fresh agent, blind; 63 tool calls,
15 min (trial 1: 133 calls, 26 min). The curl limited the target fit to ~0.2 mm even with
`--region`; the board was moved slightly between the photos, so `triangulate` could not work
and the agent estimated heights from the change in magnification (its own script).

| Dimension | Caliper | Trial 2 | Within band? |
|---|---|---|---|
| Board length (connector → switch) | 20.3 | 19.8 ±0.3 | **no, −0.5** |
| Board width | 20 | 19.7 ±0.3 | yes (at the edge) |
| Hole pitch | 15 | 15.2 ±0.2 | yes (at the edge) |
| Hole center from the connector-side edge | 3.0 | 2.95 ±0.25 | yes |
| Hole centers from the side edges | 2.5 / 2.5 | 2.4 / 1.95 ±0.3 | one yes, **one no (−0.55)** |
| Connector width × length | 10 × 7.2 | 10 × 6.5 ±0.5 | width yes, **length no (−0.7)** |
| Connector past its edge | 2 | 1.4 ±0.5 | **no, −0.6** |
| Switch body across × along | 13 × 6.3 | 12.5 × 6.45 ±0.5 | yes |
| Switch body past its edge | 1.0 | 2.0 ±0.4 | **no, +1.0** |
| Lever tip past the edge at rest | 5.0 | 4.9 ±0.5 | yes |
| PCB top above the paper | 3.3 (1.8 + 1.5) | 2.6 ±0.7 | yes (at the edge) |
| Solder joints below the PCB | up to 1.8 | 1.0 ±0.8 | yes (at the edge) |

8 of 12 within the bands, several at the edge. The overall length across the parts is right
(switch to connector 23.2 vs 23.3), so the misses come from **where the board's own edges
were placed**: on the black-and-white target a black PCB has almost no edge contrast over the
black squares, and the board's edge was picked about 0.5 mm in on the connector side and out on
the switch side.

**Trial 3 (2026-11-24), white-field target, flat, 100 %, part unmoved.** Seven photos (an
overview, a top close-up, five oblique close-ups), `calibrate` over all seven (the EXIF focal
length at 2.28× zoom was 6 % off), `rectify --camera --region`. A fresh agent, blind; 95
tool calls. Heights from matching patches across photos at trial heights (its own script) and
`triangulate` (a lever corner from three photos: rays met within 0.15 mm).

| Dimension | Caliper | Trial 3 | Within band? |
|---|---|---|---|
| Board length × width | 20.3 × 20 | 20.0 × 19.8 ±0.3 | yes (length at the edge) |
| PCB thickness | 1.5 | 1.5 ±0.2 | yes |
| Hole pitch | 15 | 15.0 ±0.15 | yes |
| Hole center from the connector-side edge | 3.0 | 3.0 ±0.3 | yes |
| Hole centers from the side edges | 2.5 / 2.5 | 2.2 / 2.5 ±0.3 | yes |
| Connector width × length | 10 × 7.2 | 10.05 × 7.05 ±0.25 | yes |
| Connector height above the PCB | 5.6 | 6.4 ±0.5 | **no, +0.8** |
| Connector past its edge | 2 | 1.9 ±0.3 | yes |
| Switch body across × along × height | 13 × 6.3 × 5.3 | 12.9 × 6.0 × 5.5 ±0.3/0.5 | yes |
| Switch body past its edge | 1.0 | 1.35 ±0.3 | **no, +0.35** |
| Lever width | 3.8 | 4.0 ±0.7 | yes |
| Lever above the PCB top (bottom–top) | 0.9–4.7 | 0.2–4.2 ±0.7 | yes |
| Lever tip past the edge at rest | 5.0 | 4.4 ±0.4 | **no, −0.6** (spring-loaded) |
| Solder joints below the PCB | up to 1.8 | 1.5 ±0.35 | yes |

**14 of 17 within the bands**, most errors 0.0–0.3 mm (trial 1: 11 of 16; trial 2: 8 of 12).
The holes, the outline, the connector's footprint and the switch's footprint, which a mount
depends on most, are all within 0.3 mm. The misses are a height (connector top, from patch
matching), a 0.35 mm switch overhang and the spring-loaded lever's rest position.

Lessons (trial 3):
- The setup is what made the difference: a flat target at 100 %, a white field, an unmoved
  part, several angles and one camera calibration for the set.
- Tools the agent wrote itself and would reuse: a **height scan** (match a patch across
  photos while sweeping z), a **rotated-rectangle fit** to edge points (the part frame's
  angle), and `overlay` on a chosen photo without editing the feature file.
- `edges --first` from outside a part finds its shadow first; scan from inside out for a
  dark part on white. `holes` on through-holes seen at an angle mixes the top edge, the bottom
  edge and the paper behind it: use small boxes and the top-view photo.

Lessons (trial 2):
- **The background matters as much as the scale:** a dark part needs a light background
  around it. Next target: markers only around the border, a plain white field in the middle
  for the part.
- **Don't touch the part between photos** (or `triangulate` needs to fit the part's motion).
- **Flatten the target** (taped on a rigid board); the curl alone was ~0.2 mm.
- Tool gaps the agent reported: `edges` should be able to return the first edge in a given
  direction (silkscreen beat the board edge); `holes` should rank concentric rings
  consistently; the `.hX.rect` file naming is undocumented; the fitted focal length on a
  square-on view reads like an alarm.

Lessons:
- **Datasheet heights of clone parts are not reliable** (both came out 0.5 mm off). When a
  height matters, the agent should ask for a caliper reading, not fall back on the drawing.
- **A ruler beside the part is not in the part's plane.** The board rests on its solder joints,
  so its top was ~2 mm above the ruler, a ~1 % scale error per mm. Better: lay the ruler *on*
  the face being measured, or give one caliper reading of an edge.
- **Bands were too tight** in round 2 (±0.3 on the outline and ±0.2 on the pitch; missed by
  0.6–0.7 and 0.35). The band must include the height-of-reference and camera-fit errors, and
  when two scale sources disagree (datasheet parts vs a ruler) the agent should say so and widen
  the band, not pick the more precise-looking one.
- **The photos caught an error in our own records** (board length 19 → 20.3): photo estimates
  are a useful cross-check of earlier measurements, not only a first source.
- **Spring-loaded parts** (the lever) move between photos; give them wide bands or measure them
  held in a known position.
- The loop works: both rounds asked for exactly the caliper readings that would settle the weak
  numbers, and resuming the agent kept its earlier work (round 2 took less than half the time).
- The agent's Write to `report.md` was refused; the main session saves the report from the
  reply.
