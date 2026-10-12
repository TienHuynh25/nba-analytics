# Evaluation

Cases live in `cases.yaml` (schema: `schema.py`). Every run uses the pinned snapshot
**`eval_2025_26_rs`**, never the live one. Its checksum is stored in `snapshots.yaml`.

## The pinned snapshot and relative time

`eval_2025_26_rs` is an as-of build (`make refresh AS_OF=<last 2025-26 regular-season game date>
SNAPSHOT_ID=eval_2025_26_rs`). It holds no game, award or title after the last regular-season game
of 2025-26. Play-In, playoffs, the 2025-26 MVP and the 2026 title are all excluded. Careers stop at
the cutoff. Its `as_of_date` is the day after that last game.

Relative time resolves against the snapshot, in US Eastern time:

| Phrase | Means on `eval_2025_26_rs` |
| --- | --- |
| this season, current, now, no season named | 2025-26 (regular season unless playoffs are named) |
| last season | 2024-25 |
| last season's playoffs, the last NBA Finals | the 2025 playoffs and Finals (2024-25) |
| today | the manifest's `as_of_date` |
| last night, last game | the last regular-season game date of 2025-26 |

The eval snapshot has no 2025-26 playoffs, so "this season's playoffs" has no data (M02 turn 2 asks
about last season's playoffs instead). Cases whose meaning depends on the date are tagged
`relative-time`. Those that name no season are also tagged `default-season`.

## Regression rule

A change merges only if, on the dev split:

1. a one-sided exact (binomial) McNemar test against the last accepted run, on the discordant
   cases, shows no significant drop at **α = 0.05** (docs/decisions/0005-v3-resolutions.md);
2. no case tagged `critical` (all-time records, refusals, Q85) moves from pass to fail;
3. no unverified number is shown.

The held-out split runs only at phase gates and releases.
