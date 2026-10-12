# Board: open work (current phase: 1 close-out for Gate 1, with 2.x authoring in parallel)

Status values: TODO | BLOCKED | IN-PROGRESS | DONE. Nothing is delegated until the user replies `approve`.
Task IDs are Execution Plan IDs. "Done when" for each is the plan's check.

## Gate 1 close-out

| ID | Title | Agent | Cx | Status | Depends-on | Rework | Agent ID |
|---|---|---|---|---|---|---|---|
| T-1.6 | Finish backfill: 220 missing `players` pairs, triage `_failed.jsonl` (NETWORK LOCK, needs user approval) | developer | M | PARTIAL (run stopped by PM; 219 careerstats ids are persistent source gaps; NETWORK LOCK released; waits on gap-policy decision) | owner decision D-011 | 0 | |
| T-1.8 | Confirm anomaly check exists and is tested (`incremental.py`/`refresh.py`) | qa-tester | L | DONE | NONE | 0 | a2497158a097f748c |
| T-1.25f | Fix DEF-005: reader must roll back on mid-file DB corruption and tampered shots; remove 2 xfail marks | developer | H | DONE (QA verify in T-QA1) | T-ENV | T-ENV (done) | |
| T-FIX1 | Triage and fix 10 failing/erroring tests in test_domain_checks, test_as_of, test_tools_oracle (DEF-003, DEF-006, DEF-007) | developer | H | DONE (QA verify in T-QA1) | T-ENV (done) | 0 | |
| T-1.6a | Read-only analysis: do the 220 missing players have games? throttling vs gaps (NO network) | qa-tester | M | DONE | NONE | 0 | a88d31a847e0fd960 |
| T-0009 | Write decision record docs/decisions/0009-player-career-source-gaps.md | architect | L | DONE | D-011 | 0 | |
| T-1.6b | Read-only: measure successful-but-empty careerstats responses, the 22 unexplained player-seasons, early-era partial gaps, reverse direction, leader impact (NO network) | qa-tester | M | DONE | NONE | 0 | |
| T-KLEB | ONE network re-fetch of playercareerstats for 1628467 (NETWORK LOCK) | developer | M | DONE (STILL-EMPTY; Kleber stays in the seed) | D-013 | 0 | |
| T-0009a | Amend decision 0009 with T-1.6b numbers and Kleber outcome | architect | L | DONE | T-KLEB (done) | 0 | |
| T-1.20v | Independent verification of domain checks (plan 1.20) on the full build | qa-tester | M | DONE (9/9 checks pass on full data and fail on planted errors; "reviewed date" finding withdrawn: not a CLAUDE.md requirement) | T-1.19 | 0 | |
| T-REC | Hand-enter pre-1996 curated records from Basketball-Reference into `records_curated` (source URL + valid-from per row, per decision 0008); owner checks B-R terms first | developer + owner | M | BLOCKED | owner: B-R terms check, which records | 0 | |
| T-GAP2 | Wording fix (DEF-010), empty-but-successful check (DEF-011), seed to 265/211, lift xfail | developer | M | DONE (verified by T-QA2 + T-QA2b) | T-0009a (done) | 1 | afedc706c591d86c4 |
| T-QA2 | Independent verification of T-GAP + T-GAP2 | qa-tester | M | DONE (verified by T-QA2 + T-QA2b) | T-GAP2 (done) | 0 | |
| T-GAP | Implement gap policy A: seed allowlist (219 careerstats ids + commonplayerinfo 200603, one note each), backfill status reconciles to 15729, reconciliation test player_season vs game-log player-seasons, answer behaviour for uncovered players unchanged (no 0s) | developer | M | DONE (verified by T-QA2 + T-QA2b) | T-0009 (done) | T-0009 | |
| T-1.19 | Run full dbt tests on the complete build, record the pass | qa-tester | M | DONE (dbt build PASS=134, 0 warn/error/skip; 73 data tests; full data landed) | T-1.6 resolved by 0009, T-GAP2 | 0 | |
| T-1.21 | Gate 1 box-score check, 20 games vs NBA.com (`-m network`; NETWORK LOCK, needs user approval) | qa-tester | M | DONE on dev.duckdb (20/20 games match, 417 lines x 16 fields); re-run on published snapshot after T-2.1 | D-003 | 0 | |
| T-1.25 | Verify rollback meets plan "done when" (lives in `ingest/snapshots.py`) | qa-tester | H | DONE (AC-1 fixed by T-1.25f, verified T-QA1) | NONE | 0 | a36abd9fe169257ab |
| T-QA1 | Re-run `make check` after T-ENV; triage failures (DEF-003, DEF-004) | qa-tester | M | DONE | T-ENV, T-1.25f, T-FIX1 (all done) | 0 | |
| T-ENV | Repair stale `.venv/bin/pytest` shebang (DEF-001) with `uv sync --reinstall`; re-run `make test` | devops | L | DONE | NONE | 0 | |
| T-0.9 | Verify CI runs: commit/push `ci.yml`, confirm green | devops | L | DONE (PR #8; CI `check` green, run 38197969785) | D-004 (approved), T-HK1, T-HK2 | 0 | |
| T-1.4v | Verify contract tests catch mutated responses (Gate 1 item, plan 1.4) | qa-tester | L | DONE (plan done-when met: 52/52 tests; 137-case matrix 105 caught; DEF-015 found) | NONE | 0 | |
| T-SEEDS | Hand-written semantic-view query for every Stats/Mixed seed (Gate 1 item) | qa-tester | M | DONE (75/75 Stats+Mixed seeds answerable, all pass sql_guard; 0 GAP; 23 held-out ids logged) | T-1.19 | 0 | |
| T-0.9b | Commit gap-policy work to PR #8 branch, push, CI result | devops | M | DONE as delivered (head 4c08895 pushed; CI red only on DEF-017, fixed in working tree, uncommitted); final commit + CI in T-0.9c | T-GAP2, T-QA2b | 0 | |
| T-CONTRACT | Fix DEF-015: varying-header contracts reject type change / header swap / extra column / short row; validate whole raw cache | developer | H | DONE (verified by T-QA3) | T-1.4v | 0 | |
| T-GUARD | Fix DEF-016: sql_guard set operation without LIMIT; no loosening | developer | M | DONE (verified by T-QA3) | T-SEEDS | 0 | |
| T-GAP2r2 | Rework 2: guard test flags its own source once tracked (DEF-017) | developer | L | DONE (verified by T-QA3) | T-0.9b committed the file | 2 | afedc706c591d86c4 |
| T-QA3 | Independent re-verification of T-CONTRACT (matrix re-run, cache validation, no loosening), T-GUARD (mutations: set ops, rejections) and DEF-017 (desktop guard still fails on a planted file) | qa-tester | M | DONE (DEF-015/016/017 VERIFIED-FIXED; 210/210 mutations caught; 44/44 hostile SQL rejected; 954 passed) | T-CONTRACT, T-GUARD, T-GAP2r2 (all done) | 0 | |
| T-0.9c | Final commit/push of T-CONTRACT + evidence, CI on last head | devops | L | BLOCKED | T-QA3 | 0 | |
| T-G1 | Gate 1 governance review and security batch review (opus, Full tier) | governance, security-reviewer | H | TODO | all above | 0 | |

## Phase 2 authoring (parallel, no network)

| ID | Title | Agent | Cx | Status | Depends-on | Rework | Agent ID |
|---|---|---|---|---|---|---|---|
| T-2.1 | Publish pinned `eval_2025_26_rs` via as-of build | developer | H | BLOCKED | T-1.6 | 0 | |
| T-2.4 | Source-of-truth sourcing for gold values (`eval/sourcing/`) | developer | M | TODO | NONE | 0 | |
| T-2.7 | Independent gold cross-check (`eval/crosscheck/`) | qa-tester | H | BLOCKED | T-2.6 | 0 | |
| T-2.6 | Compute gold values (registry-driven, opus; any formula change needs recompute) | developer | H | BLOCKED | T-2.1 | 0 | |
| T-2.9 | Case-set audit (count gap 0) and paraphrase pre-screen | qa-tester | M | DONE (AC-3 satisfied by T-QA1: 855 passed, ruff and mypy clean) | NONE | 0 | a31cf3bd807c9c8e1 |
| T-2.9r | Owner review of 15 pre-screen flags / 170 paraphrases (`eval/reports/paraphrase-prescreen.md`) | user | n/a | TODO | T-2.9 | 0 | |
| T-2.20 | Judge calibration: 30 owner-labelled answers | qa-tester | M | BLOCKED | owner review time | 0 | |
| T-2.22 | Baseline run, record with `ACCEPT=1` | qa-tester | M | BLOCKED | T-2.6, T-2.1 | 0 | |

## Housekeeping (need user approval)

| ID | Title | Agent | Cx | Status | Depends-on | Rework | Agent ID |
|---|---|---|---|---|---|---|---|
| T-HK1 | List and delete stray `* 2.py` / `* 3.py` duplicates after diffing against the originals | developer | L | DONE | user approval (destructive) | 0 | a3a2bc8b907c283d4 |
| T-HK2 | Update CLAUDE.md status paragraph for decision 0008 | developer | L | DONE | user approval (edits CLAUDE.md) | 0 | |

Later phases (Gate 2 → 3 → 4 tasks: 3.2, 3.3, 3.17–3.20, 4.x partials, 5.x) are not on this board until Gate 1 passes.
