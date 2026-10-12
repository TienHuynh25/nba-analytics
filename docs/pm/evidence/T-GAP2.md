# T-GAP2 evidence

Logs: T-GAP2-1.log (status, scratch seed, untouched dirs), T-GAP2-2.log (lint, types, suite, full-build), T-GAP2-3.log (tool wording on a scratch copy of the dev build plus the seed table).

| Check | Evidence |
|---|---|
| 1 Wording | tests/test_career_gaps.py: test_kleber_gets_the_no_totals_sentence_in_all_three_tools, test_unlisted_player_keeps_the_old_wording, test_kleber_fallback_table_says_no_rows_and_the_new_sentence; app/format.py unchanged |
| 2 Empty-but-successful | test_empty_successful_flags_only_unseeded_players_with_regular_season_games (Kleber-like flagged, seeded/never-played/Vildoza-like/recovered not); real cache: 0 flagged, 1 (1628467, 483 RS games) with Kleber's rows removed from a scratch seed (T-GAP2-1.log) |
| 3 Seed | 242 rows, classes 203/16/1/15/6/1, 265 player-seasons, 211 players: test_seed_* |
| 4 Reconciliation | xfail removed; NBA_RECON_DB=data/build/dev.duckdb: 19 passed (unexplained 0, listed_gap 265, listed_with_rows 0, each of 22 new rows deletable-fails, reverse list pinned at 22) |
| 5 Status math | players 15509 + 220 documented = 15729 / 15729 (T-GAP2-1.log); test_status_on_the_real_cache_is_fully_accounted |
| 6 Untouched | git diff --stat for app/verifier.py, metrics, transform/semantic empty; ruff, mypy clean |
| 7 Fixture | seeds_known_player_career_gaps.parquet + schema.sql/load.sql lines added by hand (not a rebuild); tool tests run on the fixture |

Deviations and extras: app/stats_path.py fallback now appends result.notes (needed so the fallback table carries the sentence). Compare also gets the missing-seasons note. dbt_project.yml has column_types for the new seed. The dev build has no seeds table yet, so the app treats it as no gaps until a rebuild.

## Rework (DEF-013, DEF-014)
- DEF-013: tests pin the literal sentences; mutation M3 (sentence edited in app/career_gaps.py, then restored) now fails 4 tests (T-GAP2-4.log).
- DEF-014: load.sql Desktop paths were inert: DuckDB IMPORT resolves parquet files by name inside the export folder (scratch copy with a changed parquet read the changed rows; /Users/tienhuynh/Desktop/nba-analytics does not exist). load.sql now holds file names only (41 lines), ingest/fixture.py normalises after export (relativize_load_sql), imported tables equal the old fixture (41 tables, 0 mismatches). Guard test added. data/build/dev.duckdb untouched; its marts.shots view still names the Desktop path (build output, git-ignored).
