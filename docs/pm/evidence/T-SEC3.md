# T-SEC3 evidence (developer): SEC-003, SEC-004, SEC-006, SEC-009

Logs: T-SEC3-1.log (repro before), T-SEC3-2.log (same script after), T-SEC3-3.log (whole-cache
land, old vs new), T-SEC3-4.log (ruff, ruff format, mypy), T-SEC3-5.log (full pytest).
Repro script and whole-cache script: session scratchpad `sec3/repro.py`, `sec3/whole.py` (tmp dirs only).

## AC-1 before / after (T-SEC3-1.log vs T-SEC3-2.log)

| Finding | Before | After |
|---|---|---|
| SEC-003 | COPY TO shots/x.csv and EXPORT DATABASE into shots: `WRITE SUCCEEDED` x2; modes 0644/0755 | both `IOException` (cannot open / cannot create dir); modes 0444/0555 |
| SEC-004 | app holds A, B corrupt: `HealthError: no healthy snapshot available` | `rolled back to nba_20260929` |
| SEC-006 header | injected header landed, table `pwned` created: True | `ContractError` (contract; header regex also rejects with validator=None) |
| SEC-006 path | quote in work path: `ParserException` | lands |
| SEC-006 contract | renamed column landed (1 row) | `ContractError: ... breaks its contract` |
| SEC-009 build `../victim` | built outside root; victim folder rmtree'd (`precious exists: False`) | `SnapshotIdError`; precious kept |
| SEC-009 manifest id | `snapshot_id='../../evil'` accepted, db path escapes folder | `SnapshotIdError` |

Regression tests: tests/test_sec3_hardening.py (24 tests, 54 cases).

## Design notes
- `build()` seals after the manifest: contents first, marker unlinked, then the folder itself, so a
  kill mid-seal leaves a BUILDING folder that the next build removes (tested).
- `_remove_tree` (prune, BUILDING leftover, failed build): resolves the path, requires a direct
  child of the snapshots root with a valid id, not a symlink, not the `current` target; chmods
  folders only to 0755 before rmtree. Files are never chmodded (hard-linked shots are shared with
  kept snapshots; tested: nlink 7 and all kept snapshots stay 0444/0555 after prune).
- `_chmod_if` only chmods when the mode differs. Digest cache: chmod (and nlink changes) bump
  ctime, so the cache re-hashes; never a stale hit (tested).
- `health_check` opens through `app.snapshot.connect_read_only` (lazy import, circular module).
- Snapshot ids: `validate_id` in `Snapshot.__post_init__` (covers load/open/rollback), `build`,
  `point_current`, `_remove_tree`, refresh CLI `--snapshot-id` (argparse exit 2). Manifest id must
  equal folder name; `published()` and `current()` skip/ignore invalid entries (rollback proceeds).
- land: headers must match `[A-Za-z0-9_]+`, paths and column names are SQL-quoted, each kept raw
  file runs through `contracts.validate` (`validator=` parameter, default on).

## AC-2 tests edited
- tests/test_land_and_schema_gen.py: `landed()` helper and the ragged-row test pass
  `validator=None`; their synthetic 4-column CommonAllPlayers does not meet the real contract.
  Assertions unchanged.
- tests/conftest.py: autouse fixture makes a test's tmp_path folders writable at teardown.
- test_snapshots.py, test_snapshots_rollback.py (incl. SIGKILL swap), test_interfaces.py: unchanged, pass.

## AC-3 whole cache (T-SEC3-3.log)
17,447 raw files landed into the scratchpad with HEAD's land.py and the new one (validation on):
8,057,232 rows, 16 tables, 0 tables differing (columns, count, bit_xor of row hashes). Nothing
written to data/build. Time: 103 s old, 649 s new (contract validation).

## AC-4
`uv run pytest -m "not network" --ignore-glob='* [23].py'`: 1097 passed, 1 skipped, 1 deselected.
`ruff check .` clean, `ruff format --check .` 197 files formatted, `mypy` no issues in 118 files.
