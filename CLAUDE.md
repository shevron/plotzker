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

## Finishing a session

- Follow the "task finished" steps in `README.md` §7.1.
- Before handing over a CAD change, follow `README.md` §7.4, including the FEM check by the
  **`fem-analyst`** sub-agent for structural parts (§7.8). Report its verdict; never change
  loads, limits or safety factors to make a part pass without the user's agreement.

## Working style

- Deliver results the user can use directly: files in the project folder, plus a short
  summary of what changed and what's next.
