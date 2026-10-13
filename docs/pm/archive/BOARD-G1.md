# Board archive: Gate 1 (passed 2026-10-12)

DONE rows moved from BOARD.md when G1 passed. Evidence under docs/pm/evidence/.

| ID | Title | Agent | Cx | Status | Depends-on | Rework | Agent ID |
|---|---|---|---|---|---|---|---|
| T-1.8 | Confirm anomaly check exists and is tested (`incremental.py`/`refresh.py`) | qa-tester | L | DONE | NONE | 0 | a2497158a097f748c |
| T-1.25f | Fix DEF-005: reader must roll back on mid-file DB corruption and tampered shots; remove 2 xfail marks | developer | H | DONE (QA verify in T-QA1) | T-ENV | T-ENV (done) | |
| T-FIX1 | Triage and fix 10 failing/erroring tests in test_domain_checks, test_as_of, test_tools_oracle (DEF-003, DEF-006, DEF-007) | developer | H | DONE (QA verify in T-QA1) | T-ENV (done) | 0 | |
| T-1.6a | Read-only analysis: do the 220 missing players have games? throttling vs gaps (NO network) | qa-tester | M | DONE | NONE | 0 | a88d31a847e0fd960 |
| T-0009 | Write decision record docs/decisions/0009-player-career-source-gaps.md | architect | L | DONE | D-011 | 0 | |
| T-1.6b | Read-only: measure successful-but-empty careerstats responses, the 22 unexplained player-seasons, early-era partial gaps, reverse direction, leader impact (NO network) | qa-tester | M | DONE | NONE | 0 | |
| T-KLEB | ONE network re-fetch of playercareerstats for 1628467 (NETWORK LOCK) | developer | M | DONE (STILL-EMPTY; Kleber stays in the seed) | D-013 | 0 | |
| T-0009a | Amend decision 0009 with T-1.6b numbers and Kleber outcome | architect | L | DONE | T-KLEB (done) | 0 | |
| T-1.20v | Independent verification of domain checks (plan 1.20) on the full build | qa-tester | M | DONE (9/9 checks pass on full data and fail on planted errors; "reviewed date" finding withdrawn: not a CLAUDE.md requirement) | T-1.19 | 0 | |
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
| T-G1c3 | Condition 3: explain 'planted short day NOT caught' in T-1.8 evidence and link to R-001 | qa-tester | L | DONE (busiest day 2026-04-10, 15 games; 1 missing NOT flagged, 2 flagged; evidence T-1.8-7.log) | T-G1-GOV | 0 | |
| T-G1c5 | Condition 5: relationships tests on every mart (player_game.player_id, player_titles, player_advanced) or logged deviation; run on existing build | developer | M | DONE (30/30 relationships/not_null tests pass; 79635 excused narrowly via 0009 seed, class other only; QA verify in T-QA4) | T-G1-GOV | 1 | |
| T-SEC1 | Fix SEC-001/002/005 in sql_guard and sql_fallback with regression tests | developer | H | DONE (SEC-001/002/005 blocked; 27 new tests fail on HEAD; corpus 75/75 identical; hostile 44+14 rejected; recursive CTEs now rejected; repo-wide lint recheck after T-SEC3) | T-G1-SEC | 0 | |
| T-SEC2 | Fix SEC-007/008: CI permissions + SHA pins, dbt telemetry off | devops | M | DONE (permissions, persist-credentials, SHA pins verified, dbt telemetry off; QA verify in T-QA4; user pushes, token has workflow scope) | T-G1-SEC | 0 | |
| T-SEC3 | Fix SEC-003/004/006/009: snapshot read-only perms, health_check config, land header safety, snapshot id validation | developer | H | DONE (SEC-003/004/006/009 blocked; whole cache lands identical: 8,057,232 rows, 16 tables; 1097 passed; landing +~9 min with validation; QA verify in T-QA4) | T-G1-SEC | 0 | |
| T-QA4 | Independent verification of T-SEC1/2/3 and T-G1c5, then security re-review of the changed items and governance re-review | qa-tester, security-reviewer, governance | H | DONE (SEC-001..009 + condition 5 VERIFIED-FIXED; 1097 passed; 2 S4 gaps found) | T-SEC1-3, T-G1c5 (all done) | 0 | |
| T-SEC4 | Four small hardening fixes: SEC-011 temp dir, SEC-012 USING SAMPLE, DEF-018 snapshot id length, DEF-019 NUL/surrogate | developer | M | DONE after rework 1 (4GB spill cap, safe CLI test stub; 1119 passed; hazard check: 4 tests fail fast, no build) | T-QA4 | 1 | |
| T-QA5 | Verify T-SEC4 (QA a0e7e988) and security spot-check (ace810af); then governance delta | qa-tester, security-reviewer, governance | M | DONE (QA T-QA5: SEC-011/012, DEF-018/019 VERIFIED-FIXED, 1119 passed; security sign-off T-G1-SEC3); governance delta T-G1-GOV2 running | T-SEC4 (done) | 0 | |
| T-2.9 | Case-set audit (count gap 0) and paraphrase pre-screen | qa-tester | M | DONE (AC-3 satisfied by T-QA1: 855 passed, ruff and mypy clean) | NONE | 0 | a31cf3bd807c9c8e1 |
| T-HK1 | List and delete stray `* 2.py` / `* 3.py` duplicates after diffing against the originals | developer | L | DONE | user approval (destructive) | 0 | a3a2bc8b907c283d4 |
| T-HK2 | Update CLAUDE.md status paragraph for decision 0008 | developer | L | DONE | user approval (edits CLAUDE.md) | 0 | |
