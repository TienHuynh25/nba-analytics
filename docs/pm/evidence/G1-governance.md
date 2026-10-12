# Gate 1 governance review (T-G1-GOV)

Reviewer: `governance` agent (opus, read-only). Saved here by the PM because the agent cannot write files. Review date 2026-10-12; CI on head 11cb9ed was still running at review time.

**Verdict: APPROVE-WITH-CONDITIONS** (also conditional on CI passing on 11cb9ed; last green head f961f25, run 38203158984).

## Checklist (Execution Plan, Gate 1)

| Checkbox | Result | Evidence |
|---|---|---|
| All dbt tests pass (1.19) | MET | T-1.19-dbt.log: PASS=134 WARN=0 ERROR=0 SKIP=0. Note: 10 relationships tests, none on player_game.player_id, player_titles or player_advanced; plan says "on every mart" (condition 5) |
| 20 box scores match NBA.com (1.21) | MET | T-1.21.log "1 passed". Governance re-ran the sample query read-only on the rebuilt dev.duckdb and on dev.duckdb.pre-T-1.19: same 20 game ids, 417 player lines identical (EXCEPT = 0 rows both ways). Re-run on a published snapshot still required (R-022) |
| Domain checks pass and fail on planted errors (1.20) | MET | T-1.20v.md, 9/9 |
| Contract tests catch a mutated response; anomaly check catches a short day (1.4, 1.8) | MET | T-1.4v.md, T-QA3 (210/210), tests/test_anomaly_check.py:184. T-1.8-6 "planted short day NOT caught" is the +/-10% inclusive tolerance (R-001), not explained in T-1.8.md (condition 3) |
| Publish survives a crash mid-swap; rollback works (1.24, 1.25) | MET | T-1.25.md, T-1.25f.md, T-QA1.md (DEF-005 fixed) |
| Every Stats and Mixed seed answerable on semantic views | MET | T-SEEDS.md, 75/75 |

Other: invariants MET (traded-player totals, NULL for untracked, snapshot lockdown, verifier and registry unchanged since first commit). Scope MET with a note (`compare` missing-seasons note goes beyond A-005, R-019). State files vs repo: NOT-MET at review time (fixed by the PM, condition 2 and 4). D-001..D-015, ENDPOINTS.md and T-1.6a extras: INSUFFICIENT (not checked in this pass).

## Caveat rulings

- CI skips 6 tests vs 1 locally: INSUFFICIENT, skipped test names not listed (T-0.9b-ci.log:65). R-027 stays open.
- Backfill: 15509 + 220 = 15729 matches decision 0009; 242-row seed matches 0009:99 and the CSV. Accept.
- records_curated empty (curated check vacuous): accept for G1; T-REC blocked on the owner (R-021).
- Plan names ingest/publish.py and rollback.py; code is in ingest/snapshots.py: accept; plan text needs a note (R-004).
- known_boxscore_gaps 1217 rows, every row noted, none dated: accept for G1; sampled review is a G2 item (R-024).
- No playoff game in the box-score sample: accept for G1 (plan 1.21 does not stratify; R-015).

## Conditions

1. CI run 38208020407 on 11cb9ed finishes green. Owner: PM/devops.
2. DEFECTS.md statuses match the QA evidence. Owner: PM.
3. Explain the "NOT caught" line in T-1.8 evidence and link it to R-001. Owner: qa-tester.
4. PROJECT.md G1 row and repo-state section updated. Owner: PM.
5. Add relationships tests for player_game.player_id, player_titles and player_advanced, or log a deviation from 1.19's "every mart". Owner: developer.

Governance suggests R-022 (box-score re-run on the published snapshot) become a Gate 2 entry criterion, and that R-001 needs an owner decision.
