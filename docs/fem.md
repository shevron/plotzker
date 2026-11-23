# FEM checks of the plotter's printed parts

The method (writing a spec, running a check, reading a result, assembly checks, limits) is
cadder's: [`cadder/docs/fem.md`](../cadder/docs/fem.md). This page holds what is the plotter's:
which parts need a check, where its data lives, and its own modeling choices. The design of the
tooling and the plotter's FEM history are in [`fem-subagent-plan.md`](fem-subagent-plan.md). The
checks are done by the `fem-analyst` sub-agent (`.claude/agents/fem-analyst.md`).

Commands: `python -m plotzker fem NAME... [--viz]` (`make fem NAMES="..."`), `python -m
plotzker fem-status` (`make fem-status`), `python -m plotzker part NAME [--json]`.

## Which parts

| Part | Structural? | State |
|------|-------------|-------|
| `x_idler_slider`, `y_idler_slider_left`, `y_idler_mount_left/right`, `x_motor_mount`, `y_motor_mount_left`, `gantry_end_bracket_left/right`, `x_carriage`, `pen_slide`, `pen_holder_body` | yes | defined, checked |
| `y_idler_slider_right`, `y_motor_mount_right` | exact mirror images | covered by the left part (`mirror_of`) |
| `tension_idler_rail`, `tension_idler_slider` | prototype of the tensioner | not used in the machine |
| `belt_clamp` | carries belt tension through two screws | to decide |
| `zrib_hanger` | light (board weight) | to decide |
| `loom_anchor`, `loom_rail`, `zrib_guard` | no | not structural |

## Where things are

- **Parts:** a printed part is a `PrintedPart` defined at the end of its module and registered in
  `src/plotzker/parts/__init__.py` (`PARTS`).
- **Loads** shared between parts: `src/plotzker/loads.py`.
- **Materials:** `src/plotzker/materials.toml`; **print profiles:** `src/plotzker/profiles/`
  (`plotzker.materials.DEFAULT_PRINT`: `default.toml` is PETG, 0.6 mm nozzle, 0.3 mm layers, 3
  perimeters, 20 % gyroid; stiffness and strength factors 0.6, `sustained_factor` 0.5). All
  assumptions until measured; calibrating against a loaded printed part is postponed.
- **Region check:** `tests/test_part_specs.py` checks each region touches its part.
- **Verdicts:** `fem/verdicts.toml` (committed); results in `fem/results/` (git-ignored).

## Modeling choices

- Mount feet clamped by a screw: a bonded zone round the screw (`regions.bond_zone`) on top of a
  z-only support for the rest of the foot. The beam on a bracket's face plate is a support, not
  a load.
- The belt tensioner's parts build their spec from one description (`slider_fem`, `mount_fem` in
  `parts/tension_idler.py`) placed in each part's frame with a `Placement`.
- Gantry-level effects (shaft sag, extrusion bending) are hand calculations, not meshed.

## Assembly checks

The belt tensioner showed why they are needed (STATUS.md T3.19): the belt pulls the idler axle
~14 mm above the tension screw, so a couple twists the slider in its dovetail. The slider tilts
by the clearance while the mount's ridge and block bend; the idler leans.

`ASSEMBLY_CHECKS` (`src/plotzker/assembly_checks.py`) lists them; the rigid play term is
`tension_idler.dovetail_play` (worst case: slider pivoting about its plate's front end,
clearance `slide_gap`, flanks at 45°; it ignores friction and does not shrink with load).

```
python -m plotzker fem y_idler_slider_left y_idler_mount_left   # also runs y_idler_tensioner_left
python -m plotzker fem x_idler_tensioner                        # from the recorded member results
```
