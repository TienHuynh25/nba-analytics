# T-HK1 evidence: Finder duplicate cleanup

Method: find for names matching `* 2.*` / `* 3.*` (excluding .git, .venv, data/, transform/target, node_modules). Each file compared with `cmp -s` against the name with " 2"/" 3" removed. Deleted only `yes` rows with `rm --`. Empty directories removed with `rmdir` (non-recursive). Originals untouched. No git add/commit.

Summary: 66 files matched. 17 byte-identical deleted. 49 differ from their original and were kept. 0 originals missing. 6 empty directories removed. 1 out-of-pattern file (`transform/logs/dbt.log.4 2`, no extension) found and kept.

| Path | Original | Identical (cmp) | Action |
|---|---|---|---|
| `app/cli 2.py` | `app/cli.py` | no | kept (differs) |
| `app/rag/cards 2.py` | `app/rag/cards.py` | no | kept (differs) |
| `app/sql_guard 2.py` | `app/sql_guard.py` | no | kept (differs) |
| `app/stats_path 2.py` | `app/stats_path.py` | no | kept (differs) |
| `app/tools/base 2.py` | `app/tools/base.py` | no | kept (differs) |
| `app/tools/stats 2.py` | `app/tools/stats.py` | no | kept (differs) |
| `app/verifier 2.py` | `app/verifier.py` | no | kept (differs) |
| `eval/contamination 2.md` | `eval/contamination.md` | no | kept (differs) |
| `metrics/registry 2.yaml` | `metrics/registry.yaml` | no | kept (differs) |
| `metrics/rounding 2.py` | `metrics/rounding.py` | no | kept (differs) |
| `metrics/schema 2.py` | `metrics/schema.py` | no | kept (differs) |
| `pyproject 2.toml` | `pyproject.toml` | no | kept (differs) |
| `tests/fixtures/nba_fixture 2.duckdb` | `tests/fixtures/nba_fixture.duckdb` | no | kept (differs) |
| `tests/fixtures/nba_fixture 3.duckdb` | `tests/fixtures/nba_fixture.duckdb` | no | kept (differs) |
| `tests/fixtures/nba_fixture/load 3.sql` | `tests/fixtures/nba_fixture/load.sql` | yes | deleted |
| `tests/fixtures/nba_fixture/marts_awards 3.parquet` | `tests/fixtures/nba_fixture/marts_awards.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/marts_franchises 2.parquet` | `tests/fixtures/nba_fixture/marts_franchises.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_franchises 3.parquet` | `tests/fixtures/nba_fixture/marts_franchises.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_games 2.parquet` | `tests/fixtures/nba_fixture/marts_games.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_games 3.parquet` | `tests/fixtures/nba_fixture/marts_games.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_player_aliases 2.parquet` | `tests/fixtures/nba_fixture/marts_player_aliases.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_player_game 2.parquet` | `tests/fixtures/nba_fixture/marts_player_game.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_player_season 2.parquet` | `tests/fixtures/nba_fixture/marts_player_season.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_player_season_stint 2.parquet` | `tests/fixtures/nba_fixture/marts_player_season_stint.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_player_titles 2.parquet` | `tests/fixtures/nba_fixture/marts_player_titles.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_player_titles 3.parquet` | `tests/fixtures/nba_fixture/marts_player_titles.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_players 2.parquet` | `tests/fixtures/nba_fixture/marts_players.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_records 2.parquet` | `tests/fixtures/nba_fixture/marts_records.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_records 3.parquet` | `tests/fixtures/nba_fixture/marts_records.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_stat_availability 3.parquet` | `tests/fixtures/nba_fixture/marts_stat_availability.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/marts_team_aliases 2.parquet` | `tests/fixtures/nba_fixture/marts_team_aliases.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_team_aliases 3.parquet` | `tests/fixtures/nba_fixture/marts_team_aliases.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_team_season 2.parquet` | `tests/fixtures/nba_fixture/marts_team_season.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_team_season 3.parquet` | `tests/fixtures/nba_fixture/marts_team_season.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_team_titles 3.parquet` | `tests/fixtures/nba_fixture/marts_team_titles.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/marts_teams 2.parquet` | `tests/fixtures/nba_fixture/marts_teams.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/marts_teams 3.parquet` | `tests/fixtures/nba_fixture/marts_teams.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/schema 2.sql` | `tests/fixtures/nba_fixture/schema.sql` | no | kept (differs) |
| `tests/fixtures/nba_fixture/seeds_award_timing 3.parquet` | `tests/fixtures/nba_fixture/seeds_award_timing.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/seeds_known_boxscore_gaps 3.parquet` | `tests/fixtures/nba_fixture/seeds_known_boxscore_gaps.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/seeds_known_stint_total_gaps 3.parquet` | `tests/fixtures/nba_fixture/seeds_known_stint_total_gaps.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/seeds_known_team_record_gaps 3.parquet` | `tests/fixtures/nba_fixture/seeds_known_team_record_gaps.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/seeds_player_alias_seed 3.parquet` | `tests/fixtures/nba_fixture/seeds_player_alias_seed.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/seeds_records_curated 2.parquet` | `tests/fixtures/nba_fixture/seeds_records_curated.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/seeds_records_curated 3.parquet` | `tests/fixtures/nba_fixture/seeds_records_curated.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/seeds_season_schedule 3.parquet` | `tests/fixtures/nba_fixture/seeds_season_schedule.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/seeds_stat_availability 3.parquet` | `tests/fixtures/nba_fixture/seeds_stat_availability.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/seeds_team_alias_seed 3.parquet` | `tests/fixtures/nba_fixture/seeds_team_alias_seed.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/seeds_tiebreaker_games 3.parquet` | `tests/fixtures/nba_fixture/seeds_tiebreaker_games.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/staging_int_season_type_status 2.parquet` | `tests/fixtures/nba_fixture/staging_int_season_type_status.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_int_season_type_status 3.parquet` | `tests/fixtures/nba_fixture/staging_int_season_type_status.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_stg_awards 3.parquet` | `tests/fixtures/nba_fixture/staging_stg_awards.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/staging_stg_franchise_history 2.parquet` | `tests/fixtures/nba_fixture/staging_stg_franchise_history.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_stg_franchise_history 3.parquet` | `tests/fixtures/nba_fixture/staging_stg_franchise_history.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_stg_player_career_totals 2.parquet` | `tests/fixtures/nba_fixture/staging_stg_player_career_totals.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_stg_player_game 2.parquet` | `tests/fixtures/nba_fixture/staging_stg_player_game.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_stg_player_season_rows 2.parquet` | `tests/fixtures/nba_fixture/staging_stg_player_season_rows.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_stg_players 2.parquet` | `tests/fixtures/nba_fixture/staging_stg_players.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_stg_standings 3.parquet` | `tests/fixtures/nba_fixture/staging_stg_standings.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/staging_stg_team_advanced 3.parquet` | `tests/fixtures/nba_fixture/staging_stg_team_advanced.parquet` | yes | deleted |
| `tests/fixtures/nba_fixture/staging_stg_team_game 2.parquet` | `tests/fixtures/nba_fixture/staging_stg_team_game.parquet` | no | kept (differs) |
| `tests/fixtures/nba_fixture/staging_stg_team_year 3.parquet` | `tests/fixtures/nba_fixture/staging_stg_team_year.parquet` | yes | deleted |
| `tests/test_backfill 2.py` | `tests/test_backfill.py` | no | kept (differs) |
| `tests/test_stats_path 2.py` | `tests/test_stats_path.py` | no | kept (differs) |
| `transform/dbt_project 2.yml` | `transform/dbt_project.yml` | no | kept (differs) |
| `transform/seeds/records_curated 2.csv` | `transform/seeds/records_curated.csv` | no | kept (differs) |

Directories (empty; original directory exists; removed with rmdir):

| Path | Original | Identical | Action |
|---|---|---|---|
| `.github/workflows 2` | `.github/workflows` | empty dir, n/a | deleted (rmdir) |
| `docs/decisions 2` | `docs/decisions` | empty dir, n/a | deleted (rmdir) |
| `transform/models/marts 2` | `transform/models/marts` | empty dir, n/a | deleted (rmdir) |
| `transform/models/semantic 2` | `transform/models/semantic` | empty dir, n/a | deleted (rmdir) |
| `transform/models/staging 2` | `transform/models/staging` | empty dir, n/a | deleted (rmdir) |
| `transform/tests/domain 2` | `transform/tests/domain` | empty dir, n/a | deleted (rmdir) |

Out of pattern (not " 2."/" 3." with extension), kept, reported:

| Path | Original | Identical | Action |
|---|---|---|---|
| `transform/logs/dbt.log.4 2` | `transform/logs/dbt.log.4` (not checked) | not compared | kept (out of scope) |

Git status before/after: `docs/pm/evidence/T-HK1-status-before.txt` and `docs/pm/evidence/T-HK1-status-after.txt` are identical.
Remaining matches after cleanup: 50 (49 differing files plus the out-of-pattern log), listed by the final find.
