# T-G1c5: mart test coverage (plan 1.19)
Plan 1.19: "dbt tests: unique, not null and relationships on every mart | All pass."

| mart | unique | not_null | relationships |
|---|---|---|---|
| players | player_id | player_id, name | n/a (root) |
| player_aliases | (player_id, alias_norm) | player_id | player_id -> players |
| franchises | franchise_id | franchise_id | n/a (root) |
| teams | (team_id, first_season_start) | franchise_id | franchise_id -> franchises |
| games | game_id | key cols | home/away_team_id -> franchises |
| player_game | (game_id, player_id) | game_id, player_id | game_id -> games; **NEW** player_id -> players (excludes class 'other' of known_player_career_gaps, i.e. 79635, decision 0009) |
| player_season_stint | (player_id, season, season_type, team_id) | player_id, team_id | player_id -> players; **NEW** team_id -> franchises |
| player_season | (player_id, season, season_type) | player_id, season, gp | player_id -> players |
| team_season | (team_id, season, season_type) | team_id | team_id -> franchises |
| team_titles | season | season, franchise_id | franchise_id -> franchises |
| awards | none (deviation: a player can share an award/season) | player_id, award, season | player_id -> players |
| records | none (deviation: no natural key; records share names across kinds/ranks) | record, value, valid_from | **NEW** player_id -> players (nulls ignored) |
| stat_availability | stat | stat, first_season_start | none (deviation: reference table) |
| player_titles | (player_id, season) | **NEW** player_id, franchise_id | **NEW** player_id -> players, franchise_id -> franchises |
| player_advanced | (player_id, season, season_type) | **NEW** player_id | **NEW** player_id -> players |
| team_aliases | (alias_norm, team_id) | **NEW** team_id | **NEW** team_id -> franchises |
| shots | not in _marts.yml (parquet view, outside scope) | | |

## Run 1 (before rework)
PASS=29 ERROR=1 (log T-G1c5-1.log): 63 orphan player_game rows, all player 79635 (1954-55 RS), the class `other` row of decision 0009.

## Rework (D-016)
The relationships test on player_game.player_id has a `where` that excludes only player_ids in
seeds.known_player_career_gaps with class = 'other' (one row: 79635). dbt does not allow ref() in a
test `where`, so the schema-qualified seed is named directly (comment in the YAML names 0009 and 79635).
- Existing build, same selection: `Done. PASS=30 ERROR=0 TOTAL=30` (log T-G1c5-2.log). No other process held dev.duckdb (lsof: only fileproviderd).
- Narrowness, on a scratch copy of dev.duckdb (deleted afterwards; log T-G1c5-3.log):
  - fake orphan row with id 99999999 (not in seed): test FAIL 1.
  - id 720 (seed class played-in-gamelogs) removed from players, so its 37 player_game rows (36 real + 1 fake) are orphans: test FAIL 37. Only class 'other' is excused.
