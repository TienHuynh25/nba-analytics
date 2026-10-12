# Board: open work (current phase: 1 close-out for Gate 1, with 2.x authoring in parallel)

Status values: TODO | BLOCKED | IN-PROGRESS | DONE. Nothing is delegated until the user replies `approve`.
Task IDs are Execution Plan IDs. "Done when" for each is the plan's check.

## Gate 1 close-out

| ID | Title | Agent | Cx | Status | Depends-on | Rework | Agent ID |
|---|---|---|---|---|---|---|---|
| T-1.6 | Finish backfill: 220 missing `players` pairs, triage `_failed.jsonl` (NETWORK LOCK, needs user approval) | developer | M | TODO | NONE | 0 | |
| T-1.8 | Confirm anomaly check exists and is tested (`incremental.py`/`refresh.py`) | qa-tester | L | DONE | NONE | 0 | a2497158a097f748c |
| T-1.25f | Fix DEF-005: reader must roll back on mid-file DB corruption and tampered shots; remove 2 xfail marks | developer | H | DONE (QA verify in T-QA1) | T-ENV | T-ENV (done) | |
| T-FIX1 | Triage and fix 10 failing/erroring tests in test_domain_checks, test_as_of, test_tools_oracle (DEF-003, DEF-006, DEF-007) | developer | H | DONE (QA verify in T-QA1) | T-ENV (done) | 0 | |
| T-1.19 | Run full dbt tests on the complete build, record the pass | qa-tester | M | TODO | T-1.6 | 0 | |
| T-1.21 | Gate 1 box-score check, 20 games vs NBA.com (`-m network`; NETWORK LOCK, needs user approval) | qa-tester | M | TODO | T-1.6 | 0 | |
| T-1.25 | Verify rollback meets plan "done when" (lives in `ingest/snapshots.py`) | qa-tester | H | FAILED (AC-1; DEF-005) | NONE | 0 | a36abd9fe169257ab |
| T-QA1 | Re-run `make check` after T-ENV; triage failures (DEF-003, DEF-004) | qa-tester | M | IN-PROGRESS | T-ENV, T-1.25f, T-FIX1 (all done) | 0 | |
| T-ENV | Repair stale `.venv/bin/pytest` shebang (DEF-001) with `uv sync --reinstall`; re-run `make test` | devops | L | DONE | NONE | 0 | |
| T-0.9 | Verify CI runs: commit/push `ci.yml`, confirm green | devops | L | IN-PROGRESS | D-004 (approved), T-HK1, T-HK2 | 0 | |
| T-G1 | Gate 1 governance review and security batch review (opus, Full tier) | governance, security-reviewer | H | TODO | all above | 0 | |

## Phase 2 authoring (parallel, no network)

| ID | Title | Agent | Cx | Status | Depends-on | Rework | Agent ID |
|---|---|---|---|---|---|---|---|
| T-2.1 | Publish pinned `eval_2025_26_rs` via as-of build | developer | H | BLOCKED | T-1.6 | 0 | |
| T-2.4 | Source-of-truth sourcing for gold values (`eval/sourcing/`) | developer | M | TODO | NONE | 0 | |
| T-2.7 | Independent gold cross-check (`eval/crosscheck/`) | qa-tester | H | BLOCKED | T-2.6 | 0 | |
| T-2.6 | Compute gold values (registry-driven, opus; any formula change needs recompute) | developer | H | BLOCKED | T-2.1 | 0 | |
| T-2.9 | Case-set audit (count gap 0) and paraphrase pre-screen; AC-3 re-run pending T-ENV | qa-tester | M | PARTIAL | NONE | 0 | a31cf3bd807c9c8e1 |
| T-2.9r | Owner review of 15 pre-screen flags / 170 paraphrases (`eval/reports/paraphrase-prescreen.md`) | user | n/a | TODO | T-2.9 | 0 | |
| T-2.20 | Judge calibration: 30 owner-labelled answers | qa-tester | M | BLOCKED | owner review time | 0 | |
| T-2.22 | Baseline run, record with `ACCEPT=1` | qa-tester | M | BLOCKED | T-2.6, T-2.1 | 0 | |

## Housekeeping (need user approval)

| ID | Title | Agent | Cx | Status | Depends-on | Rework | Agent ID |
|---|---|---|---|---|---|---|---|
| T-HK1 | List and delete stray `* 2.py` / `* 3.py` duplicates after diffing against the originals | developer | L | DONE | user approval (destructive) | 0 | a3a2bc8b907c283d4 |
| T-HK2 | Update CLAUDE.md status paragraph for decision 0008 | developer | L | DONE | user approval (edits CLAUDE.md) | 0 | |

Later phases (Gate 2 → 3 → 4 tasks: 3.2, 3.3, 3.17–3.20, 4.x partials, 5.x) are not on this board until Gate 1 passes.
