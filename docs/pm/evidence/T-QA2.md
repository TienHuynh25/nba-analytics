# T-QA2 evidence (independent QA of T-GAP / T-GAP2)
Logs: T-QA2-1.log (test_career_gaps, 19 passed), T-QA2-2.log (full suite: 873 passed, 1 skipped, 1 deselected). ruff clean, mypy strict clean (117 files). git diff --stat app/verifier.py metrics transform/semantic: empty.

## 7 checks
1 Wording VERIFIED (tests + scratch run; literal not pinned, see DEF-QA-a). 2 Empty-but-successful VERIFIED (real cache 0 flagged; Kleber rows removed from scratch seed: 1 flagged, 1628467, 483 RS games). 3 Seed VERIFIED (242 rows; 203/16/1/15/6/1; 22 season rows, 8 players; 0 dups; 0 empty notes; reviewed 2026-10-11). 4 Reconciliation VERIFIED (NBA_RECON_DB=dev.duckdb). 5 Status VERIFIED (15509 + 220 = 15729/15729). 6 Untouched VERIFIED. 7 Fixture VERIFIED by equivalence (see below); rebuild not run.

## Mutations (scratch copy of repo, original untouched)
- M1 delete one new seed row (Kleber 2025-26 RS): test_full_build_reconciles + 2 seed-count tests FAIL. Delete a whole-player row: same 3 FAIL; status shows 15728/15729 MISSING 1.
- M2 add seeded (1501, 2000-01 RS) that has a player_season row: test_full_build_reconciles + 2 count tests FAIL.
- M3 change NO_TOTALS wording in app/career_gaps.py: 19 passed (NOT detected; tests import the constant).

## Fixture
ingest.fixture.build() rmtree's tests/fixtures/nba_fixture and needs raw cache + dbt; not run. Equivalence: fixture parquet vs transform/seeds CSV: 242 rows, identical (a==b True).

## Wording (scratch DB + seed table)
Kleber get_player_stats / get_career: rows [] , note "The source has no season totals for this player." compare: LeBron row + "The source has no season totals for this player. Player id: 1628467." Hennessy 1956-57: rows [] + same sentence + "The source is missing season totals for this player for: 1956-57 regular season. The totals here exclude those seasons."; career 1955-56 only, points 196 plus missing note. No 0 produced.

## T-QA2b (re-verify DEF-013, DEF-014)
Log: T-QA2b-1.log (full suite 875 passed, 1 skipped, 1 deselected; ruff clean; mypy clean, 117 files).
Mutations in scratch (tests use literals, e.g. line 36 and 315): sentence changed -> 5 FAILED; missing-seasons sentence changed -> 3 FAILED; "Player id" suffix in app/tools/stats.py changed -> 2 FAILED (the desktop-path guard fails in scratch only because there is no .git; it passes in the repo).
DEF-014: grep -c '/Users/' load.sql = 0; Desktop path does not exist; guard test + relativize test pass; scratch copy with the seed parquet cut to 3 rows imported 3 rows (original 242), so files are read by name.
Recon test: one run failed while data/build/dev.duckdb was being rebuilt by another process (mtime 22:53); the rerun passed.
