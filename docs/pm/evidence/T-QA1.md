# T-QA1 evidence (qa-tester)
- Full suite `uv run pytest -m "not network" --ignore-glob='* [23].py' -rfEx`: 855 passed, 1 deselected, exit 0 (T-QA1-1.log).
- ruff check clean; ruff format --check: 171 files formatted; mypy: no issues in 114 files (T-QA1-2.log).
- DEF-003: mutation (overtime_only dropped from args) makes the new test raise AssertionError; tool filter at app/tools/stats.py:519-520; limit default 100 at :466. Old test used limit 25 vs min(n,100): test bug. VERIFIED-FIXED.
- DEF-005: own scenarios (T-QA1-3.log): 4 KB zero-fill at 50% and 70% of DB, single-bit flip in shots parquet: all roll back to previous. publish() at ingest/snapshots.py:309 uses health_check defaults (full, uncached); with cache pre-warmed then tampered, publish raises HealthError. VERIFIED-FIXED.
- DEF-006/007: stray-seed dbt parse failure; transform/.dbtignore added; domain-check and as-of tests pass in the full run. VERIFIED-FIXED.
- Sensitive files: git diff vs HEAD for metrics/registry.yaml, app/verifier.py, eval/cases.yaml, transform/seeds: empty; no mtime change in last day. NONE.
