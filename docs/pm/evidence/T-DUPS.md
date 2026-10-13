# T-DUPS: Finder duplicate analysis

51 untracked duplicates (all files, no directories). Ignored and left alone: `transform/logs/dbt.log.4 2`, `tests/fixtures/nba_fixture 2.duckdb`, `nba_fixture 3.duckdb`, `tests/__pycache__/*test_backfill 2*.pyc`, `*test_stats_path 2*.pyc`.

Method: sha256 in T-DUPS-before.log; `cmp` for identity; text files by line-set difference; parquet via duckdb EXCEPT both ways; originals are `<name>.<ext>` with the " N" removed. Text classification was reviewed by hand after the automatic first pass (the script flagged anything with dup-only lines; each was read and is an earlier version of code the original now supersedes). Original mtime is newer than the duplicate for all text files.

| duplicate | size dup/orig | mtime dup / orig | cmp identical | content diff | class | reason |
|---|---|---|---|---|---|---|
| app/cli 2.py | 2411/2438 | 2026-10-04 23:28:00 / 2026-10-07 21:10:33 | no | lines 68/64; dup-only 8; orig-only 4 | STALE-OLDER | older wiring (BM25Retriever direct); original uses default_retrievers (newer API) |
| app/rag/cards 2.py | 4917/5073 | 2026-10-04 22:47:44 / 2026-10-07 21:08:04 | no | lines 126/128; dup-only 1; orig-only 3 | STALE-OLDER | lacks deterministic "order by 1" (task 4.3) present in original |
| app/sql_guard 2.py | 4221/9768 | 2026-10-04 22:49:20 / 2026-10-12 01:14:41 | no | lines 114/262; dup-only 17; orig-only 153 | STALE-OLDER | 114 vs 262 lines; earlier, shorter guard; original is a superset in function |
| app/stats_path 2.py | 17071/18538 | 2026-10-04 23:32:15 / 2026-10-11 22:38:46 | no | lines 407/438; dup-only 13; orig-only 40 | STALE-OLDER | earlier _choose/_compose structure; original refactored (438 lines) |
| app/tools/base 2.py | 6037/6079 | 2026-10-04 23:19:02 / 2026-10-07 21:56:09 | no | lines 166/167; dup-only 2; orig-only 3 | STALE-OLDER | ResultValue lacks the column arg the original passes |
| app/tools/stats 2.py | 34265/36660 | 2026-10-04 23:34:38 / 2026-10-12 15:48:44 | no | lines 823/869; dup-only 32; orig-only 66 | STALE-OLDER | earlier SQL ordering/notes; original newer, +46 lines |
| app/verifier 2.py | 4648/6521 | 2026-09-30 21:21:32 / 2026-10-07 21:55:49 | no | lines 160/208; dup-only 6; orig-only 43 | STALE-OLDER | earlier verifier using metrics.rounding.extract; original newer, larger |
| eval/contamination 2.md | 857/2580 | 2026-09-30 21:43:25 / 2026-10-12 16:44:03 | no | lines 13/25; dup-only 0; orig-only 7 | STALE-OLDER | 13 vs 25 lines; every line also in original |
| metrics/registry 2.yaml | 24351/24822 | 2026-10-04 23:10:08 / 2026-10-07 21:49:16 | no | lines 693/704; dup-only 3; orig-only 8 | STALE-OLDER | registry 0.3.0; original 0.4.0 adds ts_pct_leader (decision 0007) |
| metrics/rounding 2.py | 3360/4895 | 2026-10-04 23:03:37 / 2026-10-07 21:57:43 | no | lines 84/124; dup-only 11; orig-only 47 | STALE-OLDER | 84 vs 124 lines; earlier rounding module |
| metrics/schema 2.py | 6710/6907 | 2026-09-30 21:46:11 / 2026-10-07 21:49:16 | no | lines 173/175; dup-only 2; orig-only 4 | STALE-OLDER | old era-rule check (exactly one kind); original allows games+made combo |
| pyproject 2.toml | 1212/1276 | 2026-10-07 21:00:58 / 2026-10-07 21:07:25 | no | lines 57/57; dup-only 1; orig-only 1 | STALE-OLDER | mypy override list shorter than original |
| tests/fixtures/nba_fixture/marts_franchises 2.parquet | 1650/1655 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 45/45; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_franchises 3.parquet | 1650/1655 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 45/45; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_games 2.parquet | 15808/15781 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 1321/1321; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_games 3.parquet | 15808/15781 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 1321/1321; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_player_aliases 2.parquet | 118218/117741 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 7722/7722; dup-only 1; orig-only 1 | STALE-OLDER | 1 row differs only in note wording: "best-known holder" (dup) vs "last name" (orig) |
| tests/fixtures/nba_fixture/marts_player_game 2.parquet | 391110/393050 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 28265/28265; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_player_season 2.parquet | 29982/30000 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 785/785; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_player_season_stint 2.parquet | 32282/32332 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 870/870; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_player_titles 2.parquet | 904/904 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 14/14; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_player_titles 3.parquet | 904/904 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 14/14; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_players 2.parquet | 102262/102285 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 5122/5122; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_records 2.parquet | 3046/3044 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 61/61; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_records 3.parquet | 3046/3044 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 61/61; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_team_aliases 2.parquet | 2605/2587 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 132/132; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_team_aliases 3.parquet | 2605/2587 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 132/132; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_team_season 2.parquet | 9289/9350 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 56/56; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_team_season 3.parquet | 9289/9350 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 56/56; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_teams 2.parquet | 4206/4245 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 76/76; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/marts_teams 3.parquet | 4206/4245 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 76/76; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/schema 2.sql | 51264/51469 | 2026-10-04 23:11:43 / 2026-10-11 22:38:55 | no | lines 65/66; dup-only 2; orig-only 3 | STALE-OLDER | older schema (registry 0.3.0, mis-typed records_curated, no known_player_career_gaps) |
| tests/fixtures/nba_fixture/seeds_known_stint_total_gaps 4.parquet | 1640/1640 | 2026-09-30 21:43:42 / 2026-10-07 21:51:38 | yes |  | IDENTICAL | byte-identical |
| tests/fixtures/nba_fixture/seeds_known_stint_total_gaps 5.parquet | 1640/1640 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | yes |  | IDENTICAL | byte-identical |
| tests/fixtures/nba_fixture/seeds_player_alias_seed 4.parquet | 1537/1537 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | yes |  | IDENTICAL | byte-identical |
| tests/fixtures/nba_fixture/seeds_player_alias_seed 5.parquet | 1537/1537 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | yes |  | IDENTICAL | byte-identical |
| tests/fixtures/nba_fixture/seeds_records_curated 2.parquet | 247/237 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 0/0; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/seeds_records_curated 3.parquet | 247/237 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 0/0; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_int_season_type_status 2.parquet | 1226/1225 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 4/4; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_int_season_type_status 3.parquet | 1226/1225 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 4/4; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_stg_franchise_history 2.parquet | 2667/2663 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 89/89; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_stg_franchise_history 3.parquet | 2667/2663 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 89/89; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_stg_player_career_totals 2.parquet | 30688/30707 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 988/988; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_stg_player_game 2.parquet | 432742/434644 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 28265/28265; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_stg_player_season_rows 2.parquet | 181239/181337 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 5854/5854; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_stg_players 2.parquet | 104816/104666 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 5243/5243; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/fixtures/nba_fixture/staging_stg_team_game 2.parquet | 61890/61526 | 2026-10-04 23:11:43 / 2026-10-07 21:51:38 | no | rows 2642/2642; dup-only 0; orig-only 0 | IDENTICAL | same rows/content; only parquet bytes differ (metadata/ordering) |
| tests/test_backfill 2.py | 3260/7508 | 2026-10-04 22:45:39 / 2026-10-07 21:37:20 | no | lines 81/170; dup-only 1; orig-only 66 | STALE-OLDER | 81 vs 170 lines; earlier test file, original has more tests |
| tests/test_stats_path 2.py | 6761/6762 | 2026-10-04 23:32:15 / 2026-10-07 21:37:16 | no | lines 188/188; dup-only 1; orig-only 1 | STALE-OLDER | one assertion uses prompts[1][0] vs original [-1] |
| transform/dbt_project 2.yml | 997/1341 | 2026-09-30 20:56:40 / 2026-10-12 00:37:07 | no | lines 40/48; dup-only 1; orig-only 8 | STALE-OLDER | lacks SEC-008 telemetry flag and newer seed column types |
| transform/seeds/records_curated 2.csv | 74/64 | 2026-09-30 17:42:30 / 2026-10-07 21:50:30 | no | lines 1/1; dup-only 1; orig-only 1 | STALE-OLDER | header-only (no data rows) with a wrong column set; original header is the real schema; NO hand-entered rows lost |

## Count by class

- STALE-OLDER: 18
- IDENTICAL: 33
- HAS-UNIQUE-CONTENT: 0
- CANNOT-TELL: 0

Note: 14 parquet classed IDENTICAL differ in bytes only (same rows by EXCEPT both ways); 4 are byte-identical (cmp).

## OWNER ATTENTION

None. No duplicate holds content absent from its original that looks like real work.

`transform/seeds/records_curated 2.csv` (full content), dup:
```
award,award_category,team_number,valid_from,holder_name,value,source,note
```
original `transform/seeds/records_curated.csv` (full content):
```
record,record_kind,stat,player,value,source_url,valid_from,note
```
Both are header-only; no hand-entered record rows exist in either. The duplicate is an obsolete schema.
