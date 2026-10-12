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
| G0 charter approved | n/a | ✅ |
| G1 | Gate 1: data foundation | ⬜ code and tests present; no recorded passing run; backfill 99% (see below) |
| G2 | Gate 2: test set and baseline | ⬜ no baseline report, no pinned snapshot |
| G3 | Gate 3: stats path | ⬜ only a preliminary benchmark |
| G4 | Gate 4: release | ⬜ no release report, no held-out run, no tag |

## Repo state (Explore survey, 2026-10-11; judged from file presence, no tests run)

- Code and tests exist for phases 0, 1 and 3, and most of 4 (tasks 3.x/4.x beyond the stats path are ahead of the gates, built before Gate 3).
- `make backfill-status`: reference 2/2, gamelogs 340/340, team_history 45/45, season_dash 176/176, shots 1372/1372, **players 15509/15729 (220 missing)**. Task 1.6 is not done. `_failed.jsonl` exists.
- No `data/snapshots/`, so the pinned `eval_2025_26_rs` snapshot (2.1) is not published. Gold values (2.6) and everything downstream wait on it.
- `eval/cases.yaml` has about 305 of 320 cases. No baseline (2.22), no `model-benchmark.md`, no `release-v1.md`, no git tags.
- Not started: 2.4, 2.7, 2.20, 2.22, 3.2, 3.3, 3.19, 4.12, 4.14, phase 5 (5.5 partial).
- Unverified Explore claims to check before relying on them: 1.8 anomaly check location, 1.21 scope (fixture vs full data), 3.20 need (per decision 0004).

## Divergences to resolve

- **D-A:** `CLAUDE.md` says 0.3 and G1 are open; `docs/decisions/0008-records-source-and-reviewer.md` (accepted by owner 2026-10-07) closes both. Treating them as closed; `CLAUDE.md` project-status paragraph needs a one-line update (owner's file, not edited by PM).
- **D-B:** stray Finder duplicates (`* 2.py`, `* 3.py`, `registry 2.yaml`, `pyproject 2.toml`, `contamination 2.md`) are untracked in the repo. Deleting needs your approval.
- **D-C:** much code is untracked or uncommitted, including `.github/workflows/ci.yml`, so CI may never have run.
- **D-D:** plan names `ingest/rollback.py`; rollback lives in `ingest/snapshots.py`. Plan task 1.25 "done when" needs checking against that.

## Assumptions

- A-001: phase 1 code is accepted as built; the work left for G1 is verification (full dbt tests on real data, Gate 1 network box-score test) plus finishing the 220-player backfill.
- A-002: Phase 2 test-set authoring (2.4, 2.7, 2.20 and the review tasks) may run in parallel with Phase 1 close-out, as CLAUDE.md allows.

## Open owner decisions

- None blocking. 0.3 and G1 are settled by decision 0008 (see D-A). Owner still owes: check Basketball-Reference terms before the first `records` entry, and act as paraphrase/gold/judge reviewer (blocks phase 2 time).
