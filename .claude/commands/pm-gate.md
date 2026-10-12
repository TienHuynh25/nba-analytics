---
description: Run the independent governance check for a gate and report the verdict.
argument-hint: "<1|2|3|4>"
---

Act as the PM (see `.claude/pm/PM.md`). Spawn the `governance` agent with a TASK to review gate G$ARGUMENTS against `docs/pm/PROJECT.md` and the matching "Gate" section of `Basketball Analytics RAG — Execution Plan.md`. For gates 3 and 4 also spawn `security-reviewer` (opus) on the code batch in parallel. Do not pass the gate yourself: report the verdicts and send a USER UPDATE.
