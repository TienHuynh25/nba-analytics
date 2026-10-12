# T-SEC4: SEC-011, SEC-012, snapshot id length, NUL/surrogate SQL

Developer, 2026-10-12. Logs: T-SEC4-1..7.log. Scratch scripts: scratchpad/sec4/{repro,probe11b,probe11c,probe_spillwrite,hostile}.py.

## Changes
- `app/snapshot.py`: new `spill_dir(db)`. Each process gets one private folder (`mkdtemp`, mode 0700) under the system temp dir. It is removed at exit, and only by the process that created it, so a forked child leaves it alone. Each database instance gets a unique, not-yet-created path inside that folder. `connect_read_only` runs `SET temp_directory` before `allowed_directories` and `enable_external_access=false`, because DuckDB freezes temp_directory once external access is off: setting it afterwards raised "PermissionException: Modifying the temp_directory has been disabled by configuration". `allowed_directories` is unchanged.
- `app/sql_guard.py`: `exp.TableSample` is added to `_FORBIDDEN`, which covers both `USING SAMPLE` and `TABLESAMPLE`. `check()` now rejects SQL containing a NUL, or text that cannot be encoded as UTF-8, before parsing.
- `app/sql_fallback.py`: `answer()` now also catches `ValueError` (which includes UnicodeEncodeError) and handles it the same way as `duckdb.Error`: the query counts as failed and goes to the repair attempt.
- `ingest/snapshots.py`: `SNAPSHOT_ID = [a-z0-9_]{1,64}` (`SNAPSHOT_ID_MAX = 64`), with a matching error message. The CLI, build, load/Snapshot, current, published/prune, rollback and `_remove_tree` all go through `validate_id`.
- `tests/test_sec4_hardening.py`: 21 new tests. No existing test was edited.

## Before / after (T-SEC4-1-repro.log)
| Item | Before | After |
|---|---|---|
| SEC-011: sort of 20M rows, 64 MB limit, sealed snapshot | `IOException: Failed to create directory ".../s1.duckdb.tmp"` | spills, returns 19999999 |
| SEC-012: `USING SAMPLE 10%` | guard output `... LIMIT 100 USING SAMPLE ...`, which fails with ParserException | GuardError "TABLESAMPLE is not allowed" |
| NUL: `SELECT 1\x00` | guard output `SELECT 1 AS \x00 LIMIT 100`, which fails with ParserException | GuardError "contains a NUL character" |
| Surrogate: `SELECT '\ud800'` | guard accepts; `answer()` raises an uncaught UnicodeEncodeError | GuardError; `answer()` returns ok=False after 2 attempts |
| id with 65/200/300 chars | accepted | SnapshotIdError |

On the old code, all 21 new tests fail (T-SEC4-2-tests-on-old-code.log: 21 failed). On the new code, all 21 pass.

## SEC-011: access to the spill folder (T-SEC4-3-spill-access.log, probe11b in -1)
DuckDB lets an instance use its own temp_directory even though that folder is outside `allowed_directories` under `enable_external_access=false`. The spill folder therefore works. The same exception means a locked connection can COPY into, and read from, its own spill folder once it exists. A sibling path in the per-process folder, `/etc/hosts` and the shots folder are all still refused. The parser already rejects COPY and file reads. Spill size is limited only by DuckDB's default `max_temp_directory_size` (90% of free disk).

## AC-2 (T-SEC4-4-hostile-corpus.log)
- T-QA3 hostile queries: 44/44 rejected. T-QA4 exploits: 27/27 rejected.
- 75-query corpus: 75/75 accepted. The before and after JSON (accept flag and output SQL per query) are byte-identical (`cmp`). None of the 75 uses a sample clause, a NUL or a surrogate.

## AC-3 / AC-4
- Snapshot, rollback (including the SIGKILL test), sec3/sec4 hardening, guard and fallback tests: 279 passed (T-SEC4-7).
- `uv run pytest -m "not network" --ignore-glob='* [23].py'`: 1118 passed, 1 skipped, 1 deselected (T-SEC4-5).
- `ruff check`, `ruff format --check` and `mypy` are all clean (T-SEC4-6).

## Incident during the old-code test run
The first time I ran the new tests against the old code, `test_cli_length_cap` hit the old `validate_id`, which accepted the 65-character id. `refresh.main` then started a real as-of build. I killed it after about 2 minutes, during `land`. It had:
- regenerated the semantic views (git shows no diff);
- created `data/snapshots/<65 a's>/BUILDING`;
- created `data/build/landing_work_<65 a's>/` with two ndjson files.

Both leftovers were created by that run at 01:11, and I removed them. `data/snapshots` is empty again. Nothing was published and nothing was fetched from the network, since land reads only the raw cache. The test now stubs `as_of_build`, `nightly` and `_log_run` with a SystemExit, so a regression cannot start a build. The rerun on the old code then failed safely.

## Rework 1 (PM approved both follow-ups)
Logs: T-SEC4-8..14.

### Spill cap (T-SEC4-9-spill-cap.log)
- `app/snapshot.py` adds `APP_MAX_TEMP_SIZE = "4GB"`. `connect_read_only` runs `SET max_temp_directory_size` after `temp_directory` and before the configuration lock. I checked the setting name against `duckdb_settings()` on DuckDB 1.5.6: `max_temp_directory_size`, default "90% of available disk space".
- Observed through `current_setting`: `3.7 GiB`. DuckDB reads "GB" as 10^9 bytes and displays the value in GiB.
  - With the cap, the 64 MB-limit sort still spills and returns `(19999999,)` in 0.8 s.
  - With the cap set to 1MB, the query fails with `OutOfMemoryException: failed to offload data block of size 256.0 KiB (768.0 KiB/976.5 KiB used)` after 0.1 s.
  - Raising the cap after the lock is refused with InvalidInputException.
- Tests:
  - The SEC-011 spill test now also asserts that the cap is `3.7 GiB`.
  - New test `test_spill_beyond_the_cap_is_a_duckdb_error` patches the cap to 1MB. It expects `duckdb.OutOfMemoryException` ("offload"), expects that the cap cannot be changed after the lock, and checks that the connection still works afterwards.

### Test safety (T-SEC4-10-hazard-check.log)
- New helper `tests/test_sec3_hardening.py::forbid_real_build`. It replaces `refresh.as_of_build`, `refresh.nightly`, `snapshots.build`, `snapshots.land`, `snapshots.run_dbt` and `generate_views.write` with a function that raises SystemExit carrying a message, and turns `_log_run` into a no-op.
  - Two tests use it: `test_cli_rejects_bad_snapshot_id` (an edited existing test) and `test_cli_length_cap`.
  - The assertions are unchanged: exit code 2 and "invalid snapshot id". On a regression the exit code is the message rather than 2, so the test still fails.
- The other tests that pass bad or boundary ids go to `snapshots.build` directly. They already use `_patch_build`, which stubs land, dbt and generate_views, with the config in tmp_path. The only real-path step left in them is `landing.unlink(missing_ok=True)` on a file name under data/build that does not exist.
- Hazard demo:
  - I made a scratch copy of the repo (scratchpad/sec4/repo_copy1, no data/) and replaced `validate_id` with `return snapshot_id`.
  - Both CLI tests ran there and failed: 4 failed in 0.13 s, each with "a bad snapshot id got past validation and reached a build step".
  - A ps sampler polling every 0.2 s saw 0 dbt/land processes.
  - The real data/snapshots stayed empty.

### Re-runs
- Suite `uv run pytest -m "not network" --ignore-glob='* [23].py'`: 1119 passed, 1 skipped, 1 deselected (T-SEC4-11).
- `ruff check`, `ruff format --check` and `mypy` are clean (T-SEC4-12).
- Hostile sets: 44/44 and 27/27 rejected. Corpus: 75/75 accepted, byte-identical to before (T-SEC4-13).
- data/build and data/snapshots: the listings before (T-SEC4-8) and after (T-SEC4-14) are identical.
