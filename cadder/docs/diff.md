# Design diff tool

Shows what changed in the design between two git revisions, or between a revision and the
working tree: which parts and assemblies were added, removed, changed or moved, and
what the change looks like in 3D.

```bash
cadder diff                    # HEAD → working tree (uncommitted changes)
cadder diff HEAD~3 HEAD        # any two revisions (branches, tags and hashes work)
cadder diff --open             # same, and open the HTML report
```

Needs the `diff` extra (`cadder[diff]`: numpy, manifold3d).

## What it prints

A text summary: one line per part that differs (status, volume, size and origin deltas), the
assemblies whose instances changed, the commits between the revisions, the changed source
files and any FEM verdict notes.

| Option | Effect |
|---|---|
| `--all` | also list unchanged parts and moved hardware |
| `--json` | print the comparison as JSON (no meshes) instead of text |
| `--open` | open the HTML report in the browser |
| `--serve [--port N]` | serve the report on `127.0.0.1` (default port 8765) and open it |
| `--no-html` | text only, skip the report |
| `--out DIR` | work folder (default `build/diff/`, git-ignored) |

## The HTML report

Written to `build/diff/reports/<a>..<b>/index.html`: one self-contained file with the meshes
embedded. It opens from disk, works offline and can be sent as is. It needs a current browser
(WebGL2).

- **Left:** changed parts and assemblies with a status badge. "Show unchanged" lists the rest.
  A collapsible section lists the commits, the changed source files and the parameter file's
  diff.
- **Parts:** the default **Changes** view shows the added material in green and the removed
  material in red on a faint ghost of the part, which makes even a 0.2 mm change easy to see.
  Other views: overlay of before (red) and after (blue), swipe between the two, before or after
  alone. A section plane (X, Y or Z) cuts the part open. Below the view: volume and size deltas,
  any FEM verdict note and the part's source diff.
- **Assemblies:** changed instances are drawn over the unchanged rest (green added, red removed
  or old position, blue moved or modified). Click an instance in the table to isolate it.
- **Controls:** drag to orbit, Shift-drag or right-drag to pan, wheel to zoom, double-click to
  frame everything, "Zoom to change" to frame just the change.

## How it works, and its limits

- Each revision is built in a temporary `git worktree` with its own sources (the project's
  `source_dirs`), so old commits compare correctly. Results are cached per commit in `build/diff/snapshots/`; the working
  tree is rebuilt every run. A revision or part that fails to build is reported, not fatal.
- Parts are compared by their exported STL; the added and removed material is an exact mesh
  boolean. Differences under 0.01 mm³ are ignored as noise.
- Assembly items have no names, so instances are matched by geometry: identical shape at the
  same place is unchanged; the same shape elsewhere is moved; a close one of similar size is
  modified. Instances are named after the part with the same volume, else they show
  as hardware. Assemblies are flat lists of solids, so there is no sub-assembly roll-up.
- Source diffs come from `git diff`, which ignores untracked files: `git add` a new part module
  to see it. A part can change with no diff in its own module when the project's parameter file
  (`Project.params_file`) changed.
- FEM notes only compare `fem/verdicts.toml` between the revisions ("re-checked" or "not re-run
  since this change"); `cadder fem-status` tells whether a verdict is stale.

Code: `cadder.diff`; tests: `tests/test_diff.py`. The project tells it where its sources,
parameter file and verdicts are (`cadder.project.Project`). Revisions from before a project
adopted its current layout are built through `Project.legacy_specs` (registries of older
package names). A revision is built against the cadder installed now, not the one it used.
