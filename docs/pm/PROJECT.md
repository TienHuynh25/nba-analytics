# Project charter: NBA analytics RAG assistant

Status: G0 PASSED 2026-10-11 (D-001). Active phase: Gate 1 close-out.

Source of truth: `CLAUDE.md`, `Basketball Analytics RAG — Spec.md` (v3), `Basketball Analytics RAG — Execution Plan.md`. This file only tracks PM state; it does not restate them.

- **Goal:** a fully local assistant answering NBA questions with correct, cited numbers.
- **Success metric:** ≥ 85% correct on the held-out split with zero unverified numbers (Gate 4).
- **Tier:** Full.
- **Stack:** Python 3.12 / uv, nba_api 1.11.4, DuckDB + dbt-duckdb, Ollama, ruff, mypy strict.
- **Scope/constraints:** as in CLAUDE.md invariants and the Spec; no scope beyond the Spec.

## Gates (mapped to the Execution Plan)

| PM gate | Plan gate | Status |
|---|---|---|
| G0 charter approved | n/a | ✅ 2026-10-11 |
| G1 | Gate 1: data foundation | ✅ passed 2026-10-12: governance APPROVE-WITH-CONDITIONS (G1-governance.md + T-G1-GOV2), conditions 1-5 met; security 0 Critical/High/Medium; CI green on PR #9 head 16a5c0e and on main c0d1a9b; PRs #8, #9, #4 merged |
| G2 | Gate 2: test set and baseline | ⏳ Phase 2 starting; entry criterion: box-score check re-run on the published snapshot (R-022) |
| G3 | Gate 3: stats path | ⬜ |
| G4 | Gate 4: release | ⬜ |

## Repo state (2026-10-12, after G1)

- Phase 1 code and tests are in; PR #8 (branch chore/gate1-closeout) is open and unmerged (user merges). Last green CI head f961f25; final head 11cb9ed CI running.
- Backfill: all stages complete; players 15509 + 220 documented source gaps = 15729 (decision 0009 and Amendment: 242 seed rows, 265 player-seasons, 211 players). Full dbt build PASS=134. No published snapshot exists (T-2.1 not started).
- All Gate 1 checkboxes have independent evidence; one open defect: DEF-004 (S3, stray duplicates).
- Eval: 320 case units complete; 15 paraphrase flags await owner review (T-2.9r); gold values not computed (need pinned snapshot, T-2.6).
- CLAUDE.md status paragraph updated for decision 0008 (T-HK2). Decisions 0006-0009 recorded.

## Divergences

- D-A: resolved (CLAUDE.md updated, T-HK2).
- D-B: 49-51 stray Finder duplicates still on disk; deletion pending user (D-007, D-008). `transform/.dbtignore` and `--ignore-glob` keep them from breaking builds and tests.
- D-C: resolved (work committed; CI ran green on f961f25).
- D-D: plan names ingest/publish.py and ingest/rollback.py; code is in ingest/snapshots.py (R-004); plan text needs a note.

## Assumptions

- A-001 / A-002: as before. A-005: partial-career note in get_career/get_player_stats/compare (PM clarification inside D-013, user may reverse).

## Open owner decisions

- None blocking. 0.3 and G1 are settled by decision 0008. Owner still owes: Basketball-Reference terms check and the records list for T-REC; paraphrase/gold/judge review (T-2.9r, 2.20); the anomaly floor question (R-001); merging PR #8; plan filenames (R-004); the stray duplicates (D-007/D-008).
