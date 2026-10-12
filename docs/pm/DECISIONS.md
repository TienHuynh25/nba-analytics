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
| D-009 | User refreshed gh token with `workflow` scope (option A); T-0.9 resumed | Unblocks the push and CI evidence for Gate 1 | user | 2026-10-11 |
| D-010 | PR #8 is not merged by the PM; merge is the user's call. T-0.9 evidence file edit left uncommitted to avoid another CI run | Rule 7 / avoid churn | PM | 2026-10-11 |
| D-011 | Gap policy = option A: accept and document the 219 careerstats gaps (+1 commonplayerinfo id) as reviewed source gaps (seed allowlist with a note per id), add a reconciliation test, keep the `player_season` total-row invariant; no derivation from game logs, no fallback source | Owner choice; keeps invariant, never serves a wrong number | user | 2026-10-11 |
| D-012 | PM stopped the T-1.6 backfill run (resumable) because T-1.6a showed persistent gaps and the run held the network lock for ~3 more futile hours | Evidence T-1.6a.md AC-4 | PM | 2026-10-11 |
| D-013 | Option B: amend 0009 to 265 player-seasons / 211 players with classes empty-response, early-era partial, other; first ONE re-fetch of Kleber (1628467) alone on the network; then developer fixes tool wording ('the source has no season totals for this player'), adds an empty-but-successful content check to backfill status, lifts the xfail; independent QA verifies | Owner choice | user | 2026-10-11 |
| D-014 | Dispatch T-GAP2 incl. A-005 note for partial careers (PM clarification, flagged to user) | Avoids silently low career totals; consistent with policy A | PM | 2026-10-11 |
| D-015 | Withdraw QA finding 'four allowlist seeds lack a reviewed date': CLAUDE.md requires a note per row, not a date; only the 0009 seed carries one. PM's own AC wording went beyond CLAUDE.md | Don't invent requirements (rule 8) | PM | 2026-10-11 |
