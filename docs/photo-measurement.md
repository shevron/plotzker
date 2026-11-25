# Measuring parts from photos

**Use the caliper first.** Photos are only for **flat hole patterns** and positions on one flat
face that are awkward to reach with it, expecting a few tenths of a millimeter. Heights, depths,
rounded or chamfered edges and fit-critical dimensions are measured with the caliper
(decision D39).

## 1. Taking the photo

- Print the target once (`cadder photo target`) at 100 %, measure 10 squares with the caliper,
  and tape it **flat** on a rigid surface.
- Lay the face to measure up, in the white field, with target corners visible around it.
- One photo from straight above, from further away and zoomed in 2–3× (less perspective), in
  even light, no flash glare.
- Photos go in `photos/<object>/`, a git-ignored working folder; they are never committed.

## 2. Measuring

The main session does this itself with `cadder photo`
([`cadder/docs/photo.md`](../cadder/docs/photo.md)), no sub-agent:

```bash
.venv/bin/cadder photo check photos/<object>/top.jpg
```

then
`rectify --square S --height H` onto the face, and `holes` (or `edges`) on the rectified image.
Check with the user's eye or a crop that the circles sit on the real holes. If it takes more
than a few minutes, ask for caliper readings instead.

Record the numbers in `plotzker.hardware` / `cadder.hardware` and `docs/hardware.md` as
*photo ±x*; they count as *assumed* until checked with the caliper (README §7.1).

## 3. What was tried (2026-11-24 and 25)

Benchmark: the endstop board, against the caliper values in [`hardware.md`](hardware.md).

| Approach | Time | Result |
|---|---|---|
| `photo-metrologist` sub-agent, loose photos | 18 min + 8 min | 11 of 16 within its bands; a ruler beside the part made the outline worse |
| Sub-agent with `cadder photo`, printed target | 15 min | 8 of 12 within its bands (curled print, black part on black squares) |
| Sub-agent, flat white-field target, 7 photos | 15 min | 14 of 17 within its bands; hole pitch 15.0 |
| User clicks points in several photos (code solves) | 33 min of clicking | 10 of 16 within ±0.5 mm; only 6 within its own bands |

- All five sub-agent runs took 15–26 min and 5–14 million cached tokens each, mostly model
  reasoning about where to put pixels: slower than measuring the part.
- Clicking was slow (about 21 s per click) and imprecise: board edges picked inside a light
  rim, hole centers judged by eye. Clicking the same wrong spot in several photos made the
  error bands far too narrow.
- Setup matters most: a flat target, a light background around a dark part, the part unmoved.
- Datasheet heights of cloned connectors and switches were off by 0.5 mm.
- A few target corners found in the wrong place beside the part can spoil a pose or a
  calibration (28 mm instead of 0.12 mm on one photo). `check` and `calibrate` drop them;
  `rectify` does not, so look at its reprojection error.

The agent definition and the click tool were removed; the trial's details are in git history
(`git log -- docs/photo-measurement.md`). Parts already recorded from photos (the PSU, the
XT60H-F) keep their *photo* source tags until checked with the caliper.
