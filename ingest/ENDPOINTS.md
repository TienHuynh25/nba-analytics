# Endpoint inventory (task 1.3)

Maps every core table and every Stats and Mixed seed to its `nba_api` source endpoint. It also records the
phase 1 evidence for gaps G1 and G6. Client: `nba_api==1.11.4` (pinned in `pyproject.toml`).
Probed on 2026-09-30.

## Endpoints

| Key (`data/raw/<key>/`) | `nba_api` class | Call grain | Params we set | Feeds | Seasons |
| --- | --- | --- | --- | --- | --- |
| `leaguegamelog_t` | `LeagueGameLog` | season × season type | `PlayerOrTeam=T` | `games`, `team_game` (staging) | 1946-47 → |
| `leaguegamelog_p` | `LeagueGameLog` | season × season type | `PlayerOrTeam=P` | `player_game` | 1946-47 → |
| `commonallplayers` | `CommonAllPlayers` | once | `IsOnlyCurrentSeason=0` | `players` (id, name, from/to year) | all |
| `commonplayerinfo` | `CommonPlayerInfo` | player | — | `players` (birth date, position) | all |
| `playercareerstats` | `PlayerCareerStats` | player | `PerMode=Totals` | `player_season_stint`, `player_season` (the `TOT` row), career-total check (1.20) | 1946-47 → |
| `playerawards` | `PlayerAwards` | player | — | `awards` (its `NBA Champion` rows also cross-check player titles) | all |
| `franchisehistory` | `FranchiseHistory` | once | — | `franchises`, `teams` (validity by year) | all |
| `teamyearbyyearstats` | `TeamYearByYearStats` | team (franchise) | `PerMode=Totals` | `team_season` W-L and conference rank, `team_titles` (`NBA_FINALS_APPEARANCE`) | 1946-47 → |
| `leaguedashteamstats_adv` | `LeagueDashTeamStats` | season × season type | `MeasureType=Advanced` | `team_season` off/def/net rating, pace | 1996-97 → |
| `leaguedashplayerstats_adv` | `LeagueDashPlayerStats` | season × season type | `MeasureType=Advanced` | usage rate and published TS% (registry accuracy test 3.2) | 1996-97 → |
| `leaguestandingsv3` | `LeagueStandingsV3` | season | — | `team_season` standings rank, home/road records | 1970-71 → (earlier seasons checked in 1.17) |
| `shotchartdetail` | `ShotChartDetail` | team × season × season type | `PlayerID=0`, `ContextMeasure=FGA` | `shots` | 1996-97 → |

**Call volume (full backfill).** Game logs: 80 seasons × up to 3 season types × 2 = about 480 calls.
Per-player endpoints: about 5,100 players × 3 = about 15,300 calls. Shots: 30 teams × 30 seasons × 2 types = about
1,800 calls. Other endpoints: a few hundred. At the 0.6 s throttle that is about 3 hours of request time,
before retries and response latency. `ShotChartDetail` returns a whole team-season in one call (DAL 2025-26:
7,366 shots, 23 players), so shots do not need per-player calls.

**Season types.** Game ID prefixes: `002` regular season, `004` playoffs, `005` Play-In, `006` NBA Cup final.
`LeagueGameLog(SeasonType="Regular Season")` already excludes the Cup final, as NBA.com does (2024-25: 1,230
games, all `002`). Play-In is fetched with `SeasonType="PlayIn"`. `SeasonType="IST"` returns the Cup group and
knockout games (`002`, already regular season) plus the final (`006`). Only the final is new: it is stored in
`games` with `is_cup_final = true` and kept out of regular-season stats.

**Home and away.** `LeagueGameLog` has no home/away columns. `MATCHUP` holds `"XXX vs. YYY"` for the home team and
`"XXX @ YYY"` for the away team. Periods come from team `MIN`: 240 is regulation, and each overtime adds 25 (5 players
× 5 minutes).

## Evidence for G1: first complete season of player game logs

For each season, player points in `leaguegamelog_p` were summed per (game, team) and compared with the team row
in `leaguegamelog_t`:

| Season | Team-games | Mismatched team-games | Player rows with NULL steals |
| --- | --- | --- | --- |
| 1961-62 | 720 | 6 | all (not tracked) |
| 1973-74 | 1,394 | 9 | 9,682 of 13,380 |
| 1979-80 | 1,804 | 79 | 5,016 of 17,782 |
| 1984-85 | 1,886 | 27 | 327 of 19,249 |
| 1990-91 | 2,214 | 62 | 1 |
| 1995-96 | 2,378 | 143 | 0 |
| **1996-97** | 2,378 | **0** | 0 |
| 2000-01, 2010-11, 2024-25 | — | 0 | 0 |

Every game is present in every season probed. Game counts match the schedule: 331 in 1946-47, 697 in 1970-71,
943 in 1983-84.

**Result: 1996-97 is the first season in which player game logs reconcile exactly with team totals.**
Earlier seasons have all their games, but some box scores are partial. Consequences:

1. **Domain check 1.20 (player points sum to team points)** is enforced exactly from 1996-97. Earlier
   seasons are checked against a stored allowlist of known mismatches (`transform/seeds/known_boxscore_gaps.csv`),
   so a new mismatch still fails the build. **This differs from the spec, which states the check without a
   season bound. Flagged for the owner.**
2. **Game-level stats before 1973-74 steals/blocks and before 1996-97 in general can be NULL in `player_game`**,
   even when the league tracked the stat that season. Season totals (`playercareerstats`) are complete for tracked
   stats. So seasons and careers read `player_season`, never a sum over `player_game`.
3. **Game-level records that need complete history** (Q35 career triple-doubles, counted from box scores)
   cannot come from `player_game` before 1996-97. They belong in the curated `records` table (G1). Single-game
   maxima such as Q34 are in the logs: Wilt Chamberlain's 100 points on 1962-03-02 (PHW vs. NYK) is present.
   The `records` table still holds Q34 and Q42 so their answers don't depend on how complete early logs are.
4. **Owner decision still open (G1):** may Basketball-Reference *source* the `records` table, or only *validate*
   it? The evidence above shows NBA.com box scores cannot supply career triple-doubles before 1996-97. So if
   B-Ref may only validate, Q35's gold value must come from a curated count cited to NBA.com media material.

## Evidence for G6: step-back 3s (Q76)

`ShotChartDetail` `ACTION_TYPE` distinguishes step-backs. DAL 2025-26 three-point attempts include
`Step Back Jump shot` (133) and `Step Back Bank Jump Shot` (2). **Q76 is answerable.** Its gold answer is a
percentage, not "not tracked". The registry defines a step-back 3 as `SHOT_TYPE = '3PT Field Goal'` and
`ACTION_TYPE ILIKE 'step back%'`.

## Evidence for traded players and untracked stats

`PlayerCareerStats.SeasonTotalsRegularSeason` returns one row per team plus a total row with `TEAM_ID = 0` and
`TEAM_ABBREVIATION = 'TOT'`. For Luka Doncic in 2024-25: DAL 22 GP / 619 PTS, LAL 28 GP / 789 PTS, TOT 50 GP /
1,408 PTS. `player_season` takes the `TOT` row when present, else the single team row. `player_season_stint` takes
the team rows. Untracked stats come back as NULL, not 0 (Wilt Chamberlain 1959-60: `STL`, `BLK`, `FG3M` are NULL).
His career `FG3M` is NULL, which is what Q85 needs.

## Seed → endpoint map

| Seeds | Tables | Endpoints |
| --- | --- | --- |
| Q01–Q12 player season | `player_season`, `player_season_stint` (Q08), `player_game` (Q03 triple-doubles) | `playercareerstats`, `leaguegamelog_p` |
| Q13–Q22 leaders | `player_season`, `player_game` (Q18, Q21 double-doubles, 40-point games), `players` (Q20 rookies) | `playercareerstats`, `leaguegamelog_p`, `commonallplayers` |
| Q23–Q29 comparisons | `player_season`, `team_titles` (Q29) | `playercareerstats`, `teamyearbyyearstats` |
| Q30 | `team_season` | `leaguedashteamstats_adv` |
| Q31–Q33, Q36–Q38, Q41 career records | `player_season` summed over total rows | `playercareerstats` (career totals only as a check) |
| Q34, Q35, Q42 single-game and career-count records | `records` (curated), `player_game` from 1996-97 as a check | `leaguegamelog_p` + curated source (G1) |
| Q39, Q40 | `team_titles`, `team_season` | `teamyearbyyearstats` |
| Q43–Q50 team | `team_season`, `games` (Q46 home record, Q50 streaks), `player_season_stint` (Q48) | `leaguestandingsv3`, `leaguegamelog_t`, `leaguedashteamstats_adv`, `playercareerstats` |
| Q51–Q58 games | `games`, `player_game` | `leaguegamelog_t`, `leaguegamelog_p` (Play-In and playoffs included for Q51 and Q53) |
| Q59–Q64 trends | `player_season`, league aggregates over `team_season` totals | `playercareerstats`, `teamyearbyyearstats` |
| Q71, Q72 mixed | `player_season` + advanced (TS%, usage rate) | `playercareerstats`, `leaguedashplayerstats_adv` |
| Q73–Q76 shooting | `shots` | `shotchartdetail` |
| Q77–Q80 awards | `awards`, `player_season` | `playerawards`, `playercareerstats` |
| Q85 | `player_season`, `stat_availability` | `playercareerstats` (NULL `FG3M`) |
