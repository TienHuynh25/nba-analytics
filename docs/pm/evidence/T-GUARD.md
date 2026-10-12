# T-GUARD evidence (DEF-016)
Repro before: check("SELECT player_id FROM semantic.players UNION ALL SELECT player_id FROM semantic.players")
 -> `SELECT * FROM SELECT FROM (...) AS q LIMIT 100` (DuckDB parse error).
After: `... UNION ALL SELECT player_id FROM semantic.players LIMIT 100` (executes in tests, read-only fixture).
Fix: app/sql_guard.py `_with_limit` appends LIMIT to the set-operation node (WITH stays in front); user LIMIT > 100 still lowered to 100.
Corpus: docs/pm/evidence/T-GUARD-corpus.log - 75/75 accepted before and after, output SQL identical (corpus has no set operations).
Tests: tests/test_sql_guard.py (set-op limit/cap/CTE/chained, executes in DuckDB, 14 rejection cases). Logs: T-GUARD-1.log (full suite), T-GUARD-2.log (ruff, mypy).
