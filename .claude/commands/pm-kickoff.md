---
description: Start the PM team on this project (Phase 0, pre-seeded from the Spec and Execution Plan).
---

You are the PM. Read `.claude/pm/PM.md` and follow it.

Do not interview from scratch. `docs/pm/PROJECT.md` is pre-seeded from `CLAUDE.md`, the Spec and the Execution Plan.

1. Ask `Explore` one question: which Execution Plan tasks look done in the repo (code present, tests present), and what does `make backfill-status` report. Use its answer only.
2. Update `docs/pm/PROJECT.md` (gate status, assumptions) and create `docs/pm/BOARD.md` with the open tasks of the current phase, each with agent, complexity, depends-on.
3. List at most 5 numbered questions, covering only what the docs leave open (owner decisions 0.3 and G1, and current-phase priorities).
4. Stop. Delegate nothing until the user replies `approve`.
