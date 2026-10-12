# T-SEC1 evidence (SEC-001, SEC-002, SEC-005)

Files changed: app/sql_guard.py, app/sql_fallback.py, tests/test_sql_guard.py, tests/test_sql_fallback.py.

## Fixes
- SEC-001: `_visible_ctes(table)` walks up the table's ancestors. A query's WITH is visible from its body and anything nested in it. From inside the i-th CTE only CTEs 0..i-1 are visible. Every unqualified table not resolved this way must be on the allowlist. This is never looser than before: the old global CTE set is a superset of the per-scope set. The walk is lexical rather than `traverse_scope`, so it covers every `exp.Table` the old `find_all` loop saw.
- SEC-001 extra cases found while working, now blocked: a CTE's own name inside its body (`WITH sqlite_master AS (SELECT * FROM sqlite_master) ...`, also under RECURSIVE in the anchor term) and a forward reference to a later CTE. DuckDB binds both to the catalog table. As a result, recursive CTEs are now rejected.
- SEC-002: an outer LIMIT is kept only if it is a plain `exp.Limit` whose expression is a non-string literal matching `[0-9]+` with value <= 100, and it has no `limit_options` or LIMIT BY. Anything else becomes `LIMIT 100`. That covers percent, expressions, `$1`/`?`, subqueries, decimals, `1e5`, negatives, `WITH TIES` and `FETCH FIRST`. OFFSET is kept. `run_with_timeout` uses `fetchmany(MAX_ROWS)`.
- SEC-005: SQL longer than `MAX_SQL_CHARS = 4000` is rejected before parsing. `SqlglotError` (ParseError, TokenError) and `RecursionError` map to GuardError.

## AC-1 repro (fixture copy, locked connection)
Before (T-SEC1-1-before.log): the 4 review exploits plus the WHERE-subquery, self-reference and forward-reference variants executed. They returned sqlite_master DDL (61 rows), duckdb_tables (41), the duckdb_databases absolute path and pg_settings. `LIMIT 100%`, `100 PERCENT` and `50 + 50000` returned 28,265 rows. Deep nesting raised an uncaught RecursionError, and an unterminated string an uncaught TokenError.
After (T-SEC1-2-after.log): all SEC-001 cases are rejected ("not a semantic-layer view"). Every LIMIT variant gives `LIMIT 100` and 100 rows (OFFSET kept). Nesting, TokenError and length all raise GuardError.

## AC-2 corpus (T-SEC1-corpus.log)
75/75 accepted before and after, with byte-identical output SQL. The longest query is 739 chars, under the 4,000 cap.

## AC-3 hostile sets
- T-QA3's 44: `scratchpad/qa3/guard.py` re-run gives 44/44 rejected, and its 21 allowed cases match T-QA3-3.log line for line (T-SEC1-3-qa3-after.log). The 44 are now committed as `test_qa3_hostile_still_rejected`.
- T-GUARD's 14 (`test_set_operation_rejections_unchanged`) and the 21 older rejections pass.

## Fail-before / pass-after
HEAD's guard and fallback were swapped in temporarily: 27 of the new tests failed, 118 passed (T-SEC1-4-tests-before-fix.log). With the fix all of them pass.

## AC-4
- `uv run pytest -m "not network" --ignore-glob='* [23].py'`: 1097 passed, 1 skipped, 1 deselected (T-SEC1-5-suite.log).
- Lint and types (T-SEC1-6-lint.log): ruff check/format and mypy are clean on the four T-SEC1 files. The repo-wide run has 2 E501, 2 format and 1 mypy error, all in T-SEC3 work in progress (ingest/refresh.py:81, tests/test_sec3_hardening.py:280, ingest/snapshots.py:338).
