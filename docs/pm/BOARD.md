# Board: open work (Phase 2: test set and baseline, toward Gate 2)

Status values: TODO | BLOCKED | IN-PROGRESS | DONE. Plan task IDs. Gate 1 rows are in docs/pm/archive/BOARD-G1.md.
Gate 2 entry criterion (governance, R-022): re-run the Gate 1 box-score check on the published snapshot.

| ID | Title | Agent | Cx | Status | Depends-on | Rework | Agent ID |
|---|---|---|---|---|---|---|---|
| T-QA6 | T-QA6b: independent verification of the FINAL pinned snapshot (leak scan every schema, determinism, numerics) | qa-tester | M | DONE (T-QA6b: DEF-020, DEF-021 VERIFIED-FIXED; 46 numeric checks pass; final snapshot manifest 6305f368..01e8, db 1b51001b..4d59) | T-DET (done) | Make marts deterministic (DEF-021), tie-breaks, tools ORDER BY audit, then ONE final rebuild and re-pin of eval_2025_26_rs | developer | H | IN-PROGRESS | T-2.1 r1 | 0 | a5f97d1ec6a32485b |
| T-2.1 | 0 | |
| T-2.1 | Build and freeze `eval_2025_26_rs` (AS_OF 2026-04-12, as_of_date 2026-04-13) | developer | H | DONE rework 1 (leak removed: fresh file, only marts/seeds/semantic; superseded by the final T-DET build; QA verifies only the final one) | T-1.28 done, T-1.6 resolved by 0009 | 1 | |
| T-1.21b | Re-run `-m network` box-score check against the published snapshot (Gate 2 entry; NETWORK LOCK, alone) | qa-tester | M | DONE (20/20 games, 417 lines x 16 fields match NBA.com on the pinned snapshot; same 20 games as the dev run; R-022 entry criterion met) | T-2.1 (done) | 0 | |
| T-2.6 | Compute gold values on the pinned snapshot (registry-driven; opus; Q48-v1 'Dubs' entities, R-003) | developer | H | DONE (verified by T-2.7/T-2.7b) | T-QA6b (done) | 3 | |
| T-2.7 | Independent gold cross-check against NBA.com / sources (`eval/crosscheck/`; network, alone) (scope floor, R-039: box-score spot check vs NBA.com of >= 10 games from 2025-26 incl. the last regular-season games and 5 playoff games from earlier seasons) | qa-tester | H | DONE (T-2.7b: DEF-024 VERIFIED-FIXED; H01-H04 candidate sets match an independent recompute; only H01-H04 + allowed lists changed) | T-2.6 (done) | 0 | |
| T-2.4 | Sourcing pass for gold values (`eval/sourcing/`) | developer | M | TODO | NONE | 0 | |
| T-2.22 | Baseline run, record with `ACCEPT=1` | qa-tester | M | BLOCKED | T-2.6, T-2.1 | 0 | |
| T-2.15b | Fix eval harness for the new gold shape (sql_rows reads value.rows; allowed-but-not-required numbers) without loosening unverified-number counting | developer | H | DONE (sql_rows mapping shape; allowed numbers for 16 units; 13 mutation types ~2,600 checks as expected; scratch mutant fails 10 tests; gold values/splits unchanged; 1193 passed) | T-2.6 | 0 | |
| T-2.6r | Owner review packet: docs/pm/OWNER-REVIEW.md (gold interpretations A1-A17, Basketball-Reference manual checks, paraphrases, records, other decisions) | user | n/a | TODO | T-2.7 findings (so you approve once, with the cross-check) | 0 | |
| T-2.9r | Owner review of 15 pre-screen flags / 170 paraphrases (`eval/reports/paraphrase-prescreen.md`) | user | n/a | TODO | owner time | 0 | |
| T-2.20 | Judge calibration: 30 owner-labelled answers | qa-tester + owner | M | BLOCKED | owner review time | 0 | |
| T-REC | Hand-enter pre-1996 curated records from Basketball-Reference (source URL + valid-from per row, decision 0008); owner checks B-R terms first | developer + owner | M | BLOCKED | owner: terms check + records list (R-021) | 0 | |
