# CLAUDE.md — instructions for AI agents working on the DIY Pen Plotter

Everything that applies to humans and agents alike lives in two files. Read them; don't
duplicate their content here.

- [`README.md`](README.md): goals, requirements, high-level design and decisions,
  repository layout, setup and commands, **coding standards and contribution guidelines**
  (§7: hard rules, design constraints, documentation, CAD conventions, Python and typing
  standards, comments, testing, firmware).
- [`STATUS.md`](STATUS.md): the status line, work plan, open questions, detailed decisions,
  inventory, key numbers, as-built design notes and ideas.
- [`cadder/README.md`](cadder/README.md): the generic CAD framework the plotter is built on
  (README §5, §7.4: what goes in `cadder` and what in `plotzker`; cadder never imports
  plotzker). Read it before changing anything under `cadder/`.

## Starting a session

1. Read `README.md` §7 (the rules you must follow) and the `STATUS.md` status line.
2. Read the `STATUS.md` task being worked on, the sections it references, and the linked
   `docs/` files it needs (`docs/controller.md` for electronics/firmware,
   `docs/hardware.md` for part dimensions).
3. Work on **one task at a time**, unless the user asks otherwise.
4. Before designing around an unknown dimension or fact, ask the user to measure or check
   it with the caliper rather than guessing (photos only as in `README.md` §7.9).

## Finishing a session

- Follow the "task finished" steps in `README.md` §7.1 (tick the task, record decisions,
  update `STATUS.md` and `docs/`).
- Before handing over a CAD change, follow `README.md` §7.4 (`make check`, `make test`,
  regenerate STLs and renders).
- After designing a structural printed part, or significantly changing one (anything on its load
  path), update its `Part` FEM spec and ask the **`fem-analyst`** sub-agent to check it
  (`README.md` §7.8, `cadder/docs/fem.md`, `docs/fem.md`). Report its verdict; never change loads, limits or safety
  factors to make a part pass without the user's agreement.
- Keep files on the user's computer in sync: after writing a file there, check it
  actually updated (size/timestamp). Re-send it if not.

## Working style

- Don't change a decision on your own: propose it with a short trade-off table and a
  recommendation (`README.md` §7.1).
- Deliver results the user can use directly: files in the project folder, plus a short
  summary of what changed and what's next.
