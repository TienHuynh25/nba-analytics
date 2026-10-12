# T-FIX1 root causes (DEF-003, DEF-006, DEF-007)

Fixture was NOT regenerated. No tolerance, seed allowlist, registry or app code changed.

## 1. dbt rejects a Finder-duplicate seed (DEF-006, DEF-007)

Tests: `tests/test_domain_checks.py` (8 failures), `tests/test_as_of.py::test_cutoff_inside_a_season_type_fails_the_build`
(failure), `test_no_row_after_cutoff` and `test_manifest_as_of_date_is_day_after_cutoff` (setup errors).

Cause: the stray macOS duplicate `transform/seeds/records_curated 2.csv` (a different, older
awards-shaped CSV) is parsed as seed `records_curated 2`. dbt 1.12 aborts parsing with
`Resource names cannot contain spaces: * 'seed.nba.records_curated 2'`, so every dbt invocation
fails before running anything:
- domain checks: `dbt test` writes no `run_results.json` -> `FileNotFoundError` at
  `tests/test_domain_checks.py:98`;
- as-of builds: `BuildError: dbt build failed` from the build fixture; the cutoff test expected a
  "straddles the cutoff" message and got the parse error instead.
Evidence: `docs/pm/evidence/T-FIX1-1.log`. Not a data, fixture or code bug.

Fix: new `transform/.dbtignore` (gitignore syntax, supported by dbt core) ignoring `* [0-9].*` and
`* [0-9]`, so Finder/iCloud copies are never parsed. The duplicate files are left in place
(owner decision D-007 pending). `transform/dbt_project 2.yml` is also covered (dbt only reads
`dbt_project.yml` anyway). Path: `transform/.dbtignore:1-4`.

## 2. Overtime oracle test contradicted its own arguments (DEF-003)

Test: `tests/test_tools_oracle.py::test_overtime_only_returns_only_overtime_games`.

Cause: test bug. It called `get_games` with `limit: 25` and then asserted
`len(rows) == min(n, 100)` (n = 60 overtime games in the 2024-25 fixture). The tool correctly
honours `limit` (`app/tools/stats.py:472`, schema max 100 at `app/tools/schemas.py:193`), so it
returned 25. The stale-checkout theory in DEF-003 is ruled out: `app` imports from
`/Users/tienhuynh/dev/nba-analytics`, and no traceback cites `Desktop`.

Fix: drop the explicit `limit` so the assertion tests what it states: the default cap (100)
returns every overtime game, all with `periods > 4`. This is stricter than before (60 rows
checked, not 25). Path: `tests/test_tools_oracle.py:131-132`.

## Results
- Three files: 110 passed (`T-FIX1-3.log`).
- Full suite `-m "not network" --ignore-glob='* [23].py'`: 855 passed, 1 deselected (`T-FIX1-4.log`).
- ruff/mypy on touched test file: clean (`T-FIX1-5.log`).
