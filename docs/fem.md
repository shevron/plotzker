# FEM checks of the plotter's printed parts

The method (writing a spec, running a check, reading a result, assembly checks, limits) is
cadder's: [`cadder/docs/fem.md`](../cadder/docs/fem.md). This page holds what is the plotter's:
which parts need a check, where its data lives, and its own modeling choices. Current verdicts: `make fem-status`; open ones are
listed in `STATUS.md`. The
checks are done by the `fem-analyst` sub-agent (`.claude/agents/fem-analyst.md`).

Commands: `python -m plotzker fem NAME... [--viz]` (`make fem NAMES="..."`), `python -m
plotzker fem-status` (`make fem-status`), `python -m plotzker part NAME [--json]`.

## Which parts

| Part | Structural? | State |
|------|-------------|-------|
| `idler_slider` (X and both Y idlers), `y_idler_mount_left/right`, `x_motor_mount`, `y_motor_mount_left`, `gantry_end_bracket_left/right`, `x_carriage`, `pen_slide`, `pen_holder_body` | yes | defined, checked |
| `psu_bracket` | yes | defined, checked (STATUS.md T3.31) |
| `y_motor_mount_right` | exact mirror image | covered by the left part (`mirror_of`) |
| `belt_clamp` | carries belt tension through two screws | to decide |
| `zrib_hanger` | light (board weight) | to decide |
| `x_endstop_mount`, `loom_anchor`, `loom_rail`, `zrib_guard`, `psu_hood` | no | not structural |

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
  `parts/floating_idler.py`) placed in each part's frame with a `Placement`.
- Abuse cases (pen knock, servo stall, motor jam) get a strength check only, no displacement
  limit.
- The brackets carry the force of a mount (and the motor's weight) on its footprint, but not its
  couple: the clamped joint takes that through bolt preload, and applied as forces it would pull
  on a surface that can only be pushed. The mounts' own checks include the couple.
- Gantry-level effects (shaft sag, extrusion bending) are hand calculations, not meshed.

## Assembly checks

The belt tensioner showed why they are needed (STATUS.md T3.21): the belt pulled the idler axle
~14 mm above the tension screw, so a couple twisted the slider in its dovetail; it tilted by the
clearance while the mount bent. The floating idlers (T3.22) have no play, but their slider and
mount deflections still add up.

`ASSEMBLY_CHECKS` (`src/plotzker/assembly_checks.py`) lists them. cadder's `AssemblyTerm` also
takes a rigid term (`rigid_mm`) for play that the FEM cannot see; none is in use now.

```
python -m plotzker fem idler_slider y_idler_mount_left   # also runs y_idler_tensioner_left
python -m plotzker fem x_idler_tensioner                        # from the recorded member results
```
