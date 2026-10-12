# Decisions

| ID | Decision | Reason | By | Date |
|---|---|---|---|---|
| D-001 | G0 passed: charter in PROJECT.md approved; Tier Full | User replied with answers and "Proceed" | user | 2026-10-11 |
| D-002 | Decision 0008 closes G1 (records source) and 0.3 (paraphrase reviewer); CLAUDE.md status paragraph to be updated | Owner confirmed | user | 2026-10-11 |
| D-003 | Run `make backfill` for the 220 missing `players` pairs, then the `-m network` Gate 1 box-score test, in sequence, alone under the network lock | Task 1.6 and 1.21 needed for Gate 1 | user | 2026-10-11 |
| D-004 | Commit untracked work on a feature branch and open a PR so CI runs (after stray duplicates are removed) | Gate 1 needs CI evidence | user | 2026-10-11 |
| D-005 | Delete stray `* 2.*` / `* 3.*` files only if byte-identical to their originals; any that differ are reported, not deleted | User approved deletion; non-identical files may hold unique work | user (scoped by PM) | 2026-10-11 |
| D-006 | Priority: close Gate 1 first; phase 2 authoring runs in parallel where it needs no network | User choice A | user | 2026-10-11 |
| D-007 | 49 non-identical `* 2/3.*` duplicates and `transform/logs/dbt.log.4 2` are kept and excluded from the PR commit by pathspec; per-file diff review deferred to the user | D-005 allowed deleting identical files only | PM | 2026-10-11 |
| D-008 | `transform/seeds/records_curated 2.csv` differs from `records_curated.csv`: it may hold hand-entered records data; do not delete before the user reviews it | Protect curated data | PM | 2026-10-11 |
