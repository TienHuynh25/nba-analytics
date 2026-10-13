# Evaluation

Cases live in `cases.yaml` (schema: `schema.py`). Every run uses the pinned snapshot
**`eval_2025_26_rs`**, never the live one. Its checksum is stored in `snapshots.yaml`.

## Running, and what a report proves

- `make eval` runs the dev split (`ANSWERER=stub` by default); `make eval ACCEPT=1` records the
  run as the accepted baseline (`reports/accepted.json`).
- **Before any case runs the harness verifies the pinned snapshot** (`harness/snapshot_check.py`):
  the folder exists, `manifest.json` and the database hash to `manifest_sha256` and `db_sha256` in
  `snapshots.yaml`, and `ingest.snapshots.health_check` passes (every manifest checksum, then an
  open through the app's locked reader; nothing is written). Any failure aborts the run (exit 4).
  `NBA_EVAL_SKIP_SNAPSHOT_CHECK=1` skips it for the stub answerer only (CI has no snapshot) and
  the report then says `NOT VERIFIED`.
- Report header: snapshot ID, prompt version, model, index version, git SHA (the five required
  items; `<sha>+dirty` when tracked files differ from HEAD or untracked, non-ignored files exist
  outside `eval/reports/` and `docs/pm/`, which never affect results), plus answerer, split, snapshot check (`VERIFIED` / `NOT VERIFIED`), manifest sha256,
  database sha256 and registry version.
- **Counts.** An *item* is one entry in `cases.yaml` (305). A *turn-unit* is one question asked
  (320: a multi-turn conversation is one item, several units). Reports and `python -m eval.split`
  say which they mean: dev is 213 items / 223 turn-units, held-out 97 turn-units. Stage tables
  and accuracy are per item.
- A split that did not run is reported as `not run`, including the dev - held-out difference.

## Gate 2 and the held-out policy

`make gate2` runs the dev split, then prints `GATE2 INCOMPLETE` and exits 1: Gate 2 is not
complete without held-out. `make gate2 HELDOUT_OK=1` also runs held-out and exits 0 only if the
snapshot verified and the regression rule held. It writes `reports/gate2-<git short sha>.md/.json`
(diffed against the accepted run). `HELDOUT_OK=1` is the user's approval at the plan gate; the
harness refuses `--split heldout|all` (and `make eval SPLIT=heldout`) without it. CI has no
snapshot, so the gate2 run is local and its report is committed;
`tests/test_gate2.py` checks that a committed `gate2-*.json` lists exactly the case IDs of its
split in `cases.yaml` (skipped until one is committed).

## The pinned snapshot and relative time

`eval_2025_26_rs` is an as-of build (`make refresh AS_OF=<last 2025-26 regular-season game date>
SNAPSHOT_ID=eval_2025_26_rs`). It holds no game, award or title after the last regular-season game
of 2025-26. Play-In, playoffs, the 2025-26 MVP and the 2026 title are all excluded. Careers stop at
the cutoff. Its `as_of_date` is the day after that last game.

Built 2026-10-12 from the raw cache with `AS_OF=2026-04-12` (the last game ID prefixed `002` in
the cached 2025-26 schedule and team game log; the Play-In starts 2026-04-14), so
`as_of_date` is **2026-04-13** and "last night" is **2026-04-12**.

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
