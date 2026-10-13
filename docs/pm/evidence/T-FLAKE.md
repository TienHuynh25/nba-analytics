# T-FLAKE

## Root cause (AC-1)
`test_fallback_surrogate_sql_gives_up_cleanly` itself is sound; it failed in `make()`
(tests/test_sql_fallback.py) with `ConnectionException: Can't open a connection to same database
file with a different configuration than existing connections`. DuckDB shares one instance per
file; `SqlFallback` connects via `connect_read_only` (memory_limit config, locked), `make()` opens
a plain connection first. If any earlier locked connection to the fixture file is still alive, the
plain connect fails.

Why one was alive: `run_with_timeout` (app/sql_fallback.py) starts a `threading.Timer` whose
callback `stop` closes over `con`. After `cancel()` the Timer thread is still winding down (and
the Timer sits in a reference cycle), so it keeps `con` alive until the thread exits / the cyclic
GC runs. Whether the next test sees it depends on thread and GC timing: order- and load-dependent,
never seen in isolation (a fresh process has no earlier connection).

Evidence:
- Isolated runs cannot fail (one test per process): 300 runs, see T-FLAKE-3.log.
- Old code, minimal probe, GC off, 20 loops of run_with_timeout then plain connect: 15/20 leaked.
  New code: 0/20.
- Old code, whole fast suite with `gc.disable()`: fails at test_percent_limit_returns_100_rows
  with the same ConnectionException (T-FLAKE-1.log). New code, same run: 1217 passed (T-FLAKE-2.log).

## Fix
`run_with_timeout` replaces the Timer callback with a no-op in `finally`, so the Timer never holds
the connection. Regression test `test_run_with_timeout_does_not_keep_the_connection_alive` uses a
Timer stand-in that stays referenced (deterministic); fails on old code, passes on new.

## Dirty flag
`eval/harness/report.py`: `git_sha(root)` returns `<sha>+dirty` when `git status --porcelain`
(excluding `eval/reports/`) is non-empty (tracked change or untracked non-ignored file);
`short_sha` keeps the flag in the markdown header. Tests use a tmp git repo: clean, modified,
untracked, reports/ + gitignored ignored. README updated. accepted.json untouched.

## DEF-030 (add-on)
tests/test_gate2.py: `check_gate2_report` requires split `all`, case ids == cases.yaml, snapshot
VERIFIED, manifest/db sha256 == eval/snapshots.yaml, no `+dirty`. Tests on tmp reports: correct
passes; dev-only (with all dev ids), missing id, extra id, NOT VERIFIED, +dirty, wrong sha fail.
No report committed still skips with its reason. No gate2 report created.

## Stability
Full fast suite x5 (PYTHONHASHSEED 7..35): T-FLAKE-4.log, 1217 passed each. Isolated x300: T-FLAKE-3.log.
