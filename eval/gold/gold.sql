-- Gold SQL for eval/cases.yaml (tasks 2.5/2.6). Read by eval/gold/compute_gold.py.
--
-- One block per seed, per multi-turn turn (M01.1 = turn 1 of M01) and per hard negative that
-- needs data. Paraphrases and entity variants whose gold tool call equals their seed's inherit
-- the seed's block; a variant that changes an argument needs its own block (`-- @Q01-v1`).
--
-- Block syntax:
--   -- @<block id>
--   -- key: <columns that label a row in the answer list>
--   -- numbers: <col>[=<registry metric>], ...   (or @stat_line) numbers a correct answer states
--   -- totals: <col>[=<metric>]               a column constant over the rows, stated once
--   -- required-rows: <bool col>             only these rows' numbers are required
--   -- null: <col>                           must be NULL (not-tracked cases: NULL, not 0)
--   -- ordered: true                         the question asks for a ranking (row order scored)
--   -- ties: <text>                          tie rule at the LIMIT cut (D-025)
--   <one SELECT, ending with ;>
-- A number column without "=metric" is itself a registry metric name. A number with no registry
-- metric of its own is tagged with the registry count metric whose rounding applies (0 decimals)
-- and keeps its real meaning in the column name (README "Number tags").
--
-- Conventions (eval/README.md, decision 0005): this season = 2025-26 Regular Season; last season
-- = 2024-25; last NBA Finals = 2025 Finals; last night = 2026-04-12 (as_of_date 2026-04-13).
-- Ids are exact snapshot ids (players.player_id, teams.team_id). Constants copied from
-- metrics/registry.yaml (compute_gold checks them): per_game_leader 0.70 + would-still-lead,
-- per_game_leader_playoffs 0.70, fg3_pct_leader 82 made, ts_pct_leader 0.70 + 300 FGM,
-- career_per_game 400 games or 10000 points.
-- Ranked answers keep every row tied at the cut: RANK() <= limit, then the tie-break order.

-- ============================== Player season ==============================

-- @Q01
-- key: player_name
-- numbers: points_per_game
SELECT player_id, player_name, season, season_type, games_played, points_per_game
FROM semantic.player_season_stats
WHERE player_id = 1628983 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q02
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id = 203999 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q03
-- key: player_name
-- numbers: triple_doubles
SELECT player_id, player_name, season, season_type, games_played, triple_doubles
FROM semantic.player_season_stats
WHERE player_id = 203999 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q04
-- key: player_name
-- numbers: blocks_per_game
SELECT player_id, player_name, season, season_type, games_played, blocks, blocks_per_game
FROM semantic.player_season_stats
WHERE player_id = 1641705 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q05
-- Rookie season = the player's first regular season in player_season (rule Q05).
-- key: player_name, season
-- numbers: @stat_line
WITH first AS (
  SELECT MIN(season_start) AS season_start FROM semantic.player_season_stats
  WHERE player_id = 1642843 AND season_type = 'Regular Season'
)
SELECT s.player_id, s.player_name, s.season, s.season_type, s.is_rookie_season, s.games_played,
  s.minutes_per_game, s.points_per_game, s.rebounds_per_game, s.assists_per_game,
  s.steals_per_game, s.blocks_per_game, s.field_goal_pct, s.three_point_pct, s.free_throw_pct
FROM semantic.player_season_stats s JOIN first f ON s.season_start = f.season_start
WHERE s.player_id = 1642843 AND s.season_type = 'Regular Season';

-- @Q06
-- key: player_name
-- numbers: threes_made
SELECT player_id, player_name, season, season_type, games_played, threes_made
FROM semantic.player_season_stats
WHERE player_id = 201939 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q07
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id = 2544 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q08
-- Team-scoped: the 2025-26 Lakers stint row (rule Q08), never a SUM of stints.
-- key: player_name, team_name
-- numbers: field_goal_pct
SELECT player_id, player_name, season, season_type, team_id, team_name, games_played,
  field_goals_made, field_goal_pct
FROM semantic.player_stint_stats
WHERE player_id = 1629029 AND team_id = 1610612747 AND season = '2025-26'
  AND season_type = 'Regular Season';

-- @Q09
-- key: player_name
-- numbers: minutes_per_game
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game
FROM semantic.player_season_stats
WHERE player_id = 1630162 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q10
-- key: player_name
-- numbers: free_throw_pct
SELECT player_id, player_name, season, season_type, games_played, free_throws_made, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id = 203507 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q11
-- key: player_name
-- numbers: games_played
SELECT player_id, player_name, season, season_type, games_played
FROM semantic.player_season_stats
WHERE player_id = 1628369 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q12
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id = 1628983 AND season = '2024-25' AND season_type = 'Playoffs';

-- ============================== Leaders (season) ==============================

-- @Q13
-- per_game_leader: games >= ceil(0.70 * team games), or fewer if total / that minimum would
-- still beat the best qualified average (NBA.com rule).
-- key: player_name
-- numbers: points_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, points, points_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND points_per_game IS NOT NULL
), top AS (SELECT MAX(points_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.points / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY points_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, points, points_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q14
-- key: player_name
-- numbers: rebounds_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, rebounds, rebounds_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND rebounds_per_game IS NOT NULL
), top AS (SELECT MAX(rebounds_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.rebounds / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY rebounds_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, rebounds, rebounds_per_game
FROM r WHERE rank <= 5 ORDER BY rank, player_id;

-- @Q15
-- key: player_name
-- numbers: assists_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, assists, assists_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND assists_per_game IS NOT NULL
), top AS (SELECT MAX(assists_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.assists / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY assists_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, assists, assists_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q16
-- "Most" ranks season totals, no games minimum (rule).
-- key: player_name
-- numbers: blocks
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, team_name, gp, blocks,
    RANK() OVER (ORDER BY blocks DESC) AS rank
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND blocks IS NOT NULL
)
SELECT rank, player_id, player_name, team_name, gp, blocks FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q17
-- fg3_pct_leader: at least 82 made 3-pointers, no games minimum.
-- key: player_name
-- numbers: three_point_pct
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, team_name, gp, threes_made, threes_attempted, three_point_pct,
    RANK() OVER (ORDER BY three_point_pct DESC) AS rank
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND three_point_pct IS NOT NULL
    AND threes_made >= 82
)
SELECT rank, player_id, player_name, team_name, gp, threes_made, threes_attempted,
  three_point_pct
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q18
-- key: player_name
-- numbers: double_doubles
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, team_name, gp, double_doubles,
    RANK() OVER (ORDER BY double_doubles DESC) AS rank
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND double_doubles IS NOT NULL
)
SELECT rank, player_id, player_name, team_name, gp, double_doubles FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q19
-- key: player_name
-- numbers: steals_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, steals, steals_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND steals_per_game IS NOT NULL
), top AS (SELECT MAX(steals_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.steals / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY steals_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, steals, steals_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q20
-- Rookies only (is_rookie_season), Q13 games rule; "would still lead" compares with the best
-- qualified rookie.
-- key: player_name
-- numbers: points_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, points, points_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND is_rookie_season
    AND points_per_game IS NOT NULL
), top AS (SELECT MAX(points_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.points / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY points_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, points, points_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q21
-- key: player_name
-- numbers: forty_point_games
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, team_name, gp, forty_point_games,
    RANK() OVER (ORDER BY forty_point_games DESC) AS rank
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND forty_point_games IS NOT NULL
)
SELECT rank, player_id, player_name, team_name, gp, forty_point_games FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q22
-- Plus-minus = regular-season total (rule Q22).
-- key: player_name
-- numbers: plus_minus
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, team_name, gp, plus_minus,
    RANK() OVER (ORDER BY plus_minus DESC) AS rank
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND plus_minus IS NOT NULL
)
SELECT rank, player_id, player_name, team_name, gp, plus_minus FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- ============================== Comparison ==============================

-- @Q23
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id IN (203999, 1628983) AND season = '2025-26' AND season_type = 'Regular Season'
ORDER BY player_id;

-- @Q24
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season_type, first_season, last_season, games_played,
  minutes_per_game, points_per_game, rebounds_per_game, assists_per_game, steals_per_game,
  blocks_per_game, field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_career_stats
WHERE player_id IN (2544, 893) AND season_type = 'Playoffs'
ORDER BY player_id;

-- @Q25
-- key: player_name
-- numbers: three_point_pct
SELECT player_id, player_name, season_type, threes_made, threes_attempted, three_point_pct
FROM semantic.player_career_stats
WHERE player_id IN (201939, 202691) AND season_type = 'Regular Season'
ORDER BY player_id;

-- @Q26
-- key: player_name
-- numbers: rebounds
SELECT player_id, player_name, season_type, games_played, rebounds
FROM semantic.player_career_stats
WHERE player_id IN (76375, 78049) AND season_type = 'Regular Season'
ORDER BY player_id;

-- @Q27
-- Each player's first two regular seasons, one row per season (the compare tool's
-- first_n_seasons scope); the two-season average is context, not required.
-- key: player_name, season
-- numbers: @stat_line
WITH s AS (
  SELECT player_id, player_name, season, games_played, minutes_per_game, points_per_game,
    rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game, field_goal_pct,
    three_point_pct, free_throw_pct,
    ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season_start) AS season_number
  FROM semantic.player_season_stats
  WHERE player_id IN (1641705, 1495) AND season_type = 'Regular Season'
)
SELECT player_id, player_name, season, season_number, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM s WHERE season_number <= 2
ORDER BY player_id, season;

-- @Q28
-- key: player_name
-- numbers: points_per_game
SELECT player_id, player_name, season, season_type, games_played, points, points_per_game
FROM semantic.player_season_stats
WHERE player_id IN (1630162, 1629630) AND season = '2025-26' AND season_type = 'Regular Season'
ORDER BY player_id;

-- @Q29
-- key: player_name
-- numbers: points, player_championships
SELECT player_id, player_name, season_type, points, player_championships
FROM semantic.player_career_stats
WHERE player_id IN (977, 2544) AND season_type = 'Regular Season'
ORDER BY player_id;

-- @Q30
-- key: team_name
-- numbers: defensive_rating
SELECT team_id, team_name, season, season_type, defensive_rating
FROM semantic.team_season_stats
WHERE team_id IN (1610612738, 1610612760) AND season = '2025-26'
  AND season_type = 'Regular Season'
ORDER BY team_id;

-- ============================== Records ==============================

-- @Q31
-- key: player_name
-- numbers: points
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, games_played, points, RANK() OVER (ORDER BY points DESC) AS rank
  FROM semantic.player_career_stats
  WHERE season_type = 'Regular Season' AND points IS NOT NULL
)
SELECT rank, player_id, player_name, games_played, points FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q32
-- key: player_name
-- numbers: assists
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, games_played, assists,
    RANK() OVER (ORDER BY assists DESC) AS rank
  FROM semantic.player_career_stats
  WHERE season_type = 'Regular Season' AND assists IS NOT NULL
)
SELECT rank, player_id, player_name, games_played, assists FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q33
-- key: player_name
-- numbers: threes_made
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, games_played, threes_made,
    RANK() OVER (ORDER BY threes_made DESC) AS rank
  FROM semantic.player_career_stats
  WHERE season_type = 'Regular Season' AND threes_made IS NOT NULL
)
SELECT rank, player_id, player_name, games_played, threes_made FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q34
-- Single-game record from the records table (regular season).
-- key: player_name, game_date
-- numbers: value=game_points
-- ordered: true
-- ties: every game tied for the last listed rank is included; ties list by game_date, game_id
WITH r AS (
  SELECT record, player_id, player_name, value, game_id, game_date, season, season_type,
    RANK() OVER (ORDER BY value DESC) AS rank
  FROM semantic.records WHERE stat = 'pts' AND record_kind = 'single_game'
)
SELECT rank, record, player_id, player_name, value, game_id, game_date, season, season_type
FROM r WHERE rank <= 1 ORDER BY rank, game_date, game_id, player_id;

-- @Q35
-- REGULAR-SEASON career count (playoffs excluded): Westbrook 209; 221 including playoffs (Basketball-Reference, owner-checked 2026-10-15, D-037).
-- Box-score count, partial before 1996-97; no curated career triple-double entry yet (G1 pending), as get_record does.
-- key: player_name
-- numbers: triple_doubles
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, games_played, triple_doubles,
    RANK() OVER (ORDER BY triple_doubles DESC) AS rank
  FROM semantic.player_career_stats
  WHERE season_type = 'Regular Season' AND triple_doubles IS NOT NULL
)
SELECT rank, player_id, player_name, games_played, triple_doubles,
  (SELECT COUNT(*) FROM semantic.records
   WHERE record_kind = 'career_count' AND record ILIKE '%triple-double%') AS curated_rows
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q36
-- key: player_name
-- numbers: points
SELECT player_id, player_name, season_type, first_season, last_season, games_played, points
FROM semantic.player_career_stats
WHERE player_id = 2544 AND season_type = 'Regular Season';

-- @Q37
-- career_per_game: at least 400 games or 10,000 points (registry), regular season.
-- key: player_name
-- numbers: points_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, games_played, points, points_per_game,
    RANK() OVER (ORDER BY points_per_game DESC) AS rank
  FROM semantic.player_career_stats
  WHERE season_type = 'Regular Season' AND points_per_game IS NOT NULL
    AND (games_played >= 400 OR points >= 10000)
)
SELECT rank, player_id, player_name, games_played, points, points_per_game FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q38
-- key: player_name
-- numbers: blocks
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, games_played, blocks, RANK() OVER (ORDER BY blocks DESC) AS rank
  FROM semantic.player_career_stats
  WHERE season_type = 'Regular Season' AND blocks IS NOT NULL
)
SELECT rank, player_id, player_name, games_played, blocks FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q39
-- Titles counted by franchise (registry championships).
-- key: team_name
-- numbers: championships
-- ordered: true
-- ties: every franchise tied for the last listed rank is included; ties list by franchise_id
WITH r AS (
  SELECT franchise_id, team_name, championships,
    RANK() OVER (ORDER BY championships DESC) AS rank
  FROM semantic.team_all_time_stats
  WHERE season_type = 'Regular Season' AND championships IS NOT NULL
)
SELECT rank, franchise_id, team_name, championships FROM r
WHERE rank <= 1 ORDER BY rank, franchise_id;

-- @Q40
-- Best record = highest regular-season win percentage.
-- key: team_name, season
-- numbers: wins, losses
-- ordered: true
-- ties: rank by win_pct, then more wins; every team-season still tied (same win_pct and wins)
--   at the cut is included, listed by season then team_id
WITH r AS (
  SELECT team_id, team_name, season, wins, losses, win_pct,
    RANK() OVER (ORDER BY win_pct DESC, wins DESC) AS rank
  FROM semantic.team_season_stats
  WHERE season_type = 'Regular Season' AND win_pct IS NOT NULL
)
SELECT rank, team_id, team_name, season, wins, losses, win_pct FROM r
WHERE rank <= 1 ORDER BY rank, season, team_id;

-- @Q41
-- key: player_name
-- numbers: games_played
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, games_played,
    RANK() OVER (ORDER BY games_played DESC) AS rank
  FROM semantic.player_career_stats
  WHERE season_type = 'Regular Season' AND games_played IS NOT NULL
)
SELECT rank, player_id, player_name, games_played FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q42
-- key: player_name, game_date
-- numbers: value=threes_made
-- ordered: true
-- ties: every game tied for the last listed rank is included (13 threes is a three-way tie
--   for 2nd); ties list by game_date, game_id
WITH r AS (
  SELECT record, player_id, player_name, value, game_id, game_date, season, season_type,
    RANK() OVER (ORDER BY value DESC) AS rank
  FROM semantic.records WHERE stat = 'fg3m' AND record_kind = 'single_game'
)
SELECT rank, record, player_id, player_name, value, game_id, game_date, season, season_type
FROM r WHERE rank <= 1 ORDER BY rank, game_date, game_id, player_id;

-- ============================== Team ==============================

-- @Q43
-- key: team_name
-- numbers: wins, losses
-- ordered: true
SELECT conference_rank, team_id, team_name, conference, wins, losses, win_pct
FROM semantic.team_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' AND conference = 'West'
ORDER BY conference_rank NULLS LAST, win_pct DESC, wins DESC, team_id;

-- @Q44
-- key: team_name
-- numbers: wins, losses
-- ordered: true
-- ties: rank by win_pct, then wins; every team still tied at the cut is included, by team_id
WITH r AS (
  SELECT team_id, team_name, conference, wins, losses, win_pct,
    RANK() OVER (ORDER BY win_pct DESC, wins DESC) AS rank
  FROM semantic.team_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season'
)
SELECT rank, team_id, team_name, conference, wins, losses, win_pct FROM r
WHERE rank <= 1 ORDER BY rank, team_id;

-- @Q45
-- key: team_name
-- numbers: team_points_per_game
-- ordered: true
-- ties: every team tied for the last listed rank is included; ties list by team_id
WITH r AS (
  SELECT team_id, team_name, gp, team_points_per_game,
    RANK() OVER (ORDER BY team_points_per_game DESC) AS rank
  FROM semantic.team_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season'
    AND team_points_per_game IS NOT NULL
)
SELECT rank, team_id, team_name, gp, team_points_per_game FROM r
WHERE rank <= 1 ORDER BY rank, team_id;

-- @Q46
-- key: team_name
-- numbers: home_wins, home_losses
SELECT team_id, team_name, season, season_type, home_wins, home_losses
FROM semantic.team_season_stats
WHERE team_id = 1610612747 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q47
-- key: team_name
-- numbers: net_rating
-- ordered: true
-- ties: every team tied for the last listed rank is included; ties list by team_id
WITH r AS (
  SELECT team_id, team_name, gp, net_rating, RANK() OVER (ORDER BY net_rating DESC) AS rank
  FROM semantic.team_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND net_rating IS NOT NULL
)
SELECT rank, team_id, team_name, gp, net_rating FROM r
WHERE rank <= 1 ORDER BY rank, team_id;

-- @Q48
-- Warriors stint rows only (rule Q48), Q13 games rule against the Warriors' games;
-- "would still lead" compares with the best qualified Warrior.
-- key: player_name
-- numbers: points_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, points, points_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_stint_stats
  WHERE team_id = 1610612744 AND season = '2025-26' AND season_type = 'Regular Season'
    AND points_per_game IS NOT NULL
), top AS (SELECT MAX(points_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.points / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY points_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, points, points_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q49
-- key: team_name
-- numbers: pace
-- ordered: true
-- ties: every team tied for the last listed rank is included; ties list by team_id
WITH r AS (
  SELECT team_id, team_name, gp, pace, RANK() OVER (ORDER BY pace DESC) AS rank
  FROM semantic.team_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND pace IS NOT NULL
)
SELECT rank, team_id, team_name, gp, pace FROM r
WHERE rank <= 1 ORDER BY rank, team_id;

-- ============================== Game ==============================

-- @Q50
-- Longest run of consecutive regular-season wins (games ordered by date, game_id). If two runs
-- tie, both are listed, earliest first.
-- key: first_win
-- numbers: streak=wins
WITH g AS (
  SELECT game_id, game_date,
    CASE WHEN winner_team_id = 1610612752 THEN 1 ELSE 0 END AS w
  FROM semantic.games
  WHERE season = '2025-26' AND season_type = 'Regular Season'
    AND 1610612752 IN (home_team_id, away_team_id)
), r AS (
  SELECT game_date, w,
    SUM(1 - w) OVER (ORDER BY game_date, game_id ROWS UNBOUNDED PRECEDING) AS losses_before
  FROM g
), runs AS (
  SELECT SUM(w) AS streak, MIN(game_date) AS first_win, MAX(game_date) AS last_win
  FROM r WHERE w = 1 GROUP BY losses_before
)
SELECT 1610612752 AS team_id, streak, first_win, last_win FROM runs
WHERE streak = (SELECT MAX(streak) FROM runs) ORDER BY first_win;

-- @Q51
-- Any season type (rule Q51).
-- key: game_date
-- numbers: home_pts=game_points, away_pts=game_points
SELECT game_id, game_date, season, season_type, home_team_id, home_team_name, home_pts,
  away_team_id, away_team_name, away_pts, winner_team_id
FROM semantic.games
WHERE 1610612738 IN (home_team_id, away_team_id) AND 1610612752 IN (home_team_id, away_team_id)
  AND season_type IN ('Regular Season', 'PlayIn', 'Playoffs')
ORDER BY game_date DESC, game_id DESC LIMIT 1;

-- @Q52
-- key: game_date
-- numbers: pts=game_points
SELECT game_id, player_id, player_name, game_date, season_type, matchup, pts
FROM semantic.player_game_log
WHERE player_id = 203999 AND season_type = 'Regular Season'
ORDER BY game_date DESC, game_id DESC LIMIT 1;

-- @Q53
-- Finals game = 2024-25 playoff game between the champion and its Finals opponent (team_titles).
-- key: game_date
-- numbers: home_pts=game_points, away_pts=game_points
SELECT g.game_id, g.game_date, g.season, g.home_team_name, g.home_pts, g.away_team_name,
  g.away_pts, t.champion_name
FROM semantic.games g
JOIN semantic.team_titles t ON t.season = g.season
  AND LEAST(g.home_team_id, g.away_team_id) = LEAST(t.team_id, t.opponent_team_id)
  AND GREATEST(g.home_team_id, g.away_team_id) = GREATEST(t.team_id, t.opponent_team_id)
WHERE g.season = '2024-25' AND g.season_type = 'Playoffs'
ORDER BY g.game_date DESC, g.game_id DESC LIMIT 1;

-- @Q54
-- key: player_name, game_date
-- numbers: pts=game_points
-- ordered: true
-- ties: every game tied for the last listed rank is included; ties list by game_date, game_id
WITH r AS (
  SELECT game_id, player_id, player_name, game_date, matchup, pts,
    RANK() OVER (ORDER BY pts DESC) AS rank
  FROM semantic.player_game_log
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND pts IS NOT NULL
)
SELECT rank, game_id, player_id, player_name, game_date, matchup, pts FROM r
WHERE rank <= 1 ORDER BY rank, game_date, game_id, player_id;

-- @Q55
-- Last night = 2026-04-12. Points, rebounds and assists leaders of each game; tied leaders
-- are all named (names joined in alphabetical order).
-- key: away_team_name, home_team_name
-- numbers: pts=game_points, reb=rebounds, ast=assists
WITH g AS (
  SELECT game_id, home_team_name, away_team_name, home_pts, away_pts FROM semantic.games
  WHERE game_date = '2026-04-12' AND season_type = 'Regular Season'
), b AS (
  SELECT l.game_id, l.player_name, l.pts, l.reb, l.ast,
    MAX(l.pts) OVER (PARTITION BY l.game_id) AS max_pts,
    MAX(l.reb) OVER (PARTITION BY l.game_id) AS max_reb,
    MAX(l.ast) OVER (PARTITION BY l.game_id) AS max_ast
  FROM semantic.player_game_log l JOIN g USING (game_id)
)
SELECT g.game_id, g.home_team_name, g.home_pts, g.away_team_name, g.away_pts,
  MAX(b.max_pts) AS pts,
  STRING_AGG(b.player_name, ' / ' ORDER BY b.player_name) FILTER (WHERE b.pts = b.max_pts)
    AS pts_leaders,
  MAX(b.max_reb) AS reb,
  STRING_AGG(b.player_name, ' / ' ORDER BY b.player_name) FILTER (WHERE b.reb = b.max_reb)
    AS reb_leaders,
  MAX(b.max_ast) AS ast,
  STRING_AGG(b.player_name, ' / ' ORDER BY b.player_name) FILTER (WHERE b.ast = b.max_ast)
    AS ast_leaders
FROM g JOIN b USING (game_id)
GROUP BY g.game_id, g.home_team_name, g.home_pts, g.away_team_name, g.away_pts
ORDER BY g.game_id;

-- @Q56
-- key: game_date
-- numbers: pts=game_points
-- ordered: true
SELECT game_id, player_id, player_name, game_date, matchup, pts
FROM semantic.player_game_log
WHERE player_id = 201939 AND season_type = 'Regular Season'
ORDER BY game_date DESC, game_id DESC LIMIT 5;

-- @Q57
-- The answer must give how many games went to overtime; the game list is context.
-- key: game_date
-- numbers:
-- totals: overtime_games=games_played
SELECT game_id, game_date, home_team_name, home_pts, away_team_name, away_pts, periods,
  COUNT(*) OVER () AS overtime_games
FROM semantic.games
WHERE season = '2025-26' AND season_type = 'Regular Season' AND overtime
ORDER BY game_date, game_id;

-- @Q58
-- key: game_date
-- numbers: margin=game_points
-- ordered: true
-- ties: every game tied for the last listed rank is included; ties list by game_date, game_id
WITH r AS (
  SELECT game_id, game_date, home_team_name, home_pts, away_team_name, away_pts, margin,
    RANK() OVER (ORDER BY margin DESC) AS rank
  FROM semantic.games
  WHERE season = '2025-26' AND season_type = 'Regular Season'
)
SELECT rank, game_id, game_date, home_team_name, home_pts, away_team_name, away_pts, margin
FROM r WHERE rank <= 1 ORDER BY rank, game_date, game_id;

-- ============================== Trend ==============================

-- @Q59
-- "Since 2010" = 2010-11 onward (rule).
-- key: season
-- numbers: league_three_point_attempt_rate
-- ordered: true
SELECT season, teams, league_three_point_attempt_rate
FROM semantic.league_season_stats
WHERE season_type = 'Regular Season' AND season BETWEEN '2010-11' AND '2025-26'
ORDER BY season;

-- @Q60
-- key: season
-- numbers: three_point_pct
-- ordered: true
SELECT player_id, player_name, season, games_played, threes_made, threes_attempted,
  three_point_pct
FROM semantic.player_season_stats
WHERE player_id = 1641705 AND season_type = 'Regular Season'
ORDER BY season;

-- @Q61
-- key: season
-- numbers: points_per_game
-- ordered: true
SELECT player_id, player_name, season, team_name, games_played, points_per_game
FROM semantic.player_season_stats
WHERE player_id = 2544 AND season_type = 'Regular Season'
ORDER BY season;

-- @Q62
-- "The 1990s" = 1990-91 to 1999-00; "now" = 2025-26 (rule). Required: those 11 seasons. The
-- full 1990-91..2025-26 series of the gold tool call is in the rows; higher_than_1990s compares
-- 2025-26 with the 1990s' highest season.
-- key: season
-- numbers: league_points_per_game
-- required-rows: compared
-- ordered: true
WITH s AS (
  SELECT season, league_points_per_game,
    season BETWEEN '1990-91' AND '1999-00' OR season = '2025-26' AS compared
  FROM semantic.league_season_stats
  WHERE season_type = 'Regular Season' AND season BETWEEN '1990-91' AND '2025-26'
)
SELECT season, league_points_per_game, compared,
  (SELECT league_points_per_game FROM s WHERE season = '2025-26')
    > (SELECT MAX(league_points_per_game) FROM s WHERE season BETWEEN '1990-91' AND '1999-00')
    AS higher_than_1990s
FROM s ORDER BY season;

-- @Q63
-- Last 5 seasons = 2021-22 to 2025-26 (the gold tool call).
-- key: season
-- numbers: wins
-- ordered: true
SELECT team_id, team_name, season, wins, losses
FROM semantic.team_season_stats
WHERE team_id = 1610612760 AND season_type = 'Regular Season'
  AND season BETWEEN '2021-22' AND '2025-26'
ORDER BY season;

-- @Q64
-- key: season
-- numbers: assists_per_game
-- ordered: true
WITH s AS (
  SELECT player_id, player_name, season, games_played, assists_per_game,
    assists_per_game - LAG(assists_per_game) OVER (ORDER BY season) AS change
  FROM semantic.player_season_stats
  WHERE player_id = 203999 AND season_type = 'Regular Season'
)
SELECT *, (SELECT BOOL_AND(change > 0) FROM s WHERE change IS NOT NULL)
  AS went_up_every_season
FROM s ORDER BY season;

-- ============================== Mixed (stats half) ==============================

-- @Q71
-- ts_pct_leader: 70% of team games AND 300 made field goals (decision 0007 B).
-- key: player_name
-- numbers: true_shooting_pct
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, team_name, gp, team_gp, field_goals_made, true_shooting_pct,
    RANK() OVER (ORDER BY true_shooting_pct DESC) AS rank
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season'
    AND true_shooting_pct IS NOT NULL
    AND gp >= CEIL(0.70 * team_gp) AND field_goals_made >= 300
)
SELECT rank, player_id, player_name, team_name, gp, field_goals_made, true_shooting_pct
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q72
-- Required: Jokic's usage rate (the gold tool call). Context: mean usage rate of 2025-26
-- centers (players.position starting 'Center') with at least 500 minutes.
-- key: player_name
-- numbers: usage_rate
WITH c AS (
  SELECT ROUND(AVG(s.usage_rate), 6) AS centers_avg_usage_rate, COUNT(*) AS centers
  FROM semantic.player_season_stats s JOIN semantic.players p USING (player_id)
  WHERE s.season = '2025-26' AND s.season_type = 'Regular Season'
    AND p.position LIKE 'Center%' AND s.minutes >= 500
)
SELECT s.player_id, s.player_name, s.season, s.usage_rate, c.centers_avg_usage_rate, c.centers
FROM semantic.player_season_stats s, c
WHERE s.player_id = 203999 AND s.season = '2025-26' AND s.season_type = 'Regular Season';

-- ============================== Shooting ==============================

-- @Q73
-- Shot attempts by zone, 2025-26 regular season; share is context.
-- key: zone
-- numbers: shot_attempts
-- ordered: true
WITH z AS (
  SELECT zone, COUNT(*) AS shot_attempts, COUNT(*) FILTER (WHERE made) AS made
  FROM semantic.shots
  WHERE player_id = 201939 AND season = '2025-26' AND season_type = 'Regular Season'
  GROUP BY zone
)
SELECT zone, shot_attempts, made,
  ROUND(shot_attempts / SUM(shot_attempts) OVER (), 6) AS share
FROM z ORDER BY shot_attempts DESC, zone;

-- @Q74
-- key: player_name
-- numbers: restricted_area_fg_pct
SELECT player_id, player_name, season, season_type, restricted_area_fg_pct
FROM semantic.player_season_stats
WHERE player_id = 203507 AND season = '2025-26' AND season_type = 'Regular Season';

-- @Q75
-- key: player_name
-- numbers: corner_threes_made
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, team_name, gp, corner_threes_made,
    RANK() OVER (ORDER BY corner_threes_made DESC) AS rank
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season'
    AND corner_threes_made IS NOT NULL
)
SELECT rank, player_id, player_name, team_name, gp, corner_threes_made FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q76
-- key: player_name
-- numbers: step_back_three_pct
SELECT player_id, player_name, season, season_type, step_back_three_pct
FROM semantic.player_season_stats
WHERE player_id = 1629029 AND season = '2025-26' AND season_type = 'Regular Season';

-- ============================== Awards ==============================

-- @Q77
-- key: player_name
-- numbers: @stat_line
SELECT a.player_id, a.player_name, a.season, s.games_played, s.minutes_per_game,
  s.points_per_game, s.rebounds_per_game, s.assists_per_game, s.steals_per_game,
  s.blocks_per_game, s.field_goal_pct, s.three_point_pct, s.free_throw_pct
FROM semantic.awards a
JOIN semantic.player_season_stats s
  ON s.player_id = a.player_id AND s.season = a.season AND s.season_type = 'Regular Season'
WHERE a.award = 'NBA Most Valuable Player' AND a.season = '2024-25'
ORDER BY a.player_id;

-- @Q78
-- key: player_name
-- numbers: awards=mvp_awards
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH c AS (
  SELECT player_id, player_name, COUNT(*) AS awards, MIN(season) AS first_season,
    MAX(season) AS last_season
  FROM semantic.awards WHERE award = 'NBA Most Valuable Player'
  GROUP BY player_id, player_name
), r AS (SELECT *, RANK() OVER (ORDER BY awards DESC) AS rank FROM c)
SELECT rank, player_id, player_name, awards, first_season, last_season FROM r
WHERE rank <= 1 ORDER BY rank, player_id;

-- @Q79
-- "In 2024" = the 2023-24 award (rule Q79). No number to state; the name is scored.
-- key: player_name
-- numbers:
SELECT player_id, player_name, season, team_name
FROM semantic.awards
WHERE award = 'NBA Rookie of the Year' AND season = '2023-24'
ORDER BY player_id;

-- @Q80
-- key: player_name
-- numbers: all_star_selections
SELECT player_id, player_name, all_star_selections
FROM semantic.player_career_stats
WHERE player_id = 2544 AND season_type = 'Regular Season';

-- ============================== Scope limits ==============================

-- @Q85
-- Not tracked: the 3-point line arrived in 1979-80; his career ended before it, so the value
-- is NULL (not 0).
-- key: player_name
-- numbers:
-- null: threes_made
SELECT c.player_id, c.player_name, c.first_season, c.last_season, c.threes_made,
  a.stat, a.first_season AS first_season_tracked
FROM semantic.player_career_stats c, semantic.stat_availability a
WHERE c.player_id = 76375 AND c.season_type = 'Regular Season' AND a.stat = 'fg3m';

-- ============================== Hard negatives ==============================

-- @H01
-- Clarify (D-027): every snapshot player the name resolves to under app/entities.py's
-- shared-name rule: a bare surname matches every player whose last name equals it
-- (accent- and case-insensitive), any era and any number of games.
-- key: player_name
-- numbers:
SELECT player_id, name AS player_name, from_year, to_year
FROM semantic.players WHERE lower(strip_accents(last_name)) = 'holiday' ORDER BY player_id;

-- @H02
-- Clarify (D-027): every player with surname Ball (shared-name rule, any era).
-- key: player_name
-- numbers:
SELECT player_id, name AS player_name, from_year, to_year
FROM semantic.players WHERE lower(strip_accents(last_name)) = 'ball' ORDER BY player_id;

-- @H03
-- Clarify (D-027): every player with surname Antetokounmpo (shared-name rule, any era),
-- including Kostas (22 games, 2018-21).
-- key: player_name
-- numbers:
SELECT player_id, name AS player_name, from_year, to_year
FROM semantic.players WHERE lower(strip_accents(last_name)) = 'antetokounmpo'
ORDER BY player_id;

-- @H04
-- Clarify (D-027): initial + surname ("J. Williams") matches every player with surname
-- Williams whose name starts with J (shared-name rule), any era; the resolver does not
-- filter by season, so "this season" does not narrow the set (owner to confirm).
-- key: player_name
-- numbers:
SELECT player_id, name AS player_name, from_year, to_year
FROM semantic.players
WHERE lower(strip_accents(last_name)) = 'williams' AND lower(strip_accents(name)) LIKE 'j%'
ORDER BY player_id;

-- @H05
-- Opinion: career regular-season stat lines side by side, no verdict.
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season_type, first_season, last_season, games_played,
  minutes_per_game, points_per_game, rebounds_per_game, assists_per_game, steals_per_game,
  blocks_per_game, field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_career_stats
WHERE player_id IN (2544, 893) AND season_type = 'Regular Season'
ORDER BY player_id;

-- @H07
-- Opinion: career regular-season stat lines; Wilt's steals, blocks and 3P% are NULL (not
-- tracked), so they are not numbers to state.
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season_type, first_season, last_season, games_played,
  minutes_per_game, points_per_game, rebounds_per_game, assists_per_game, steals_per_game,
  blocks_per_game, field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_career_stats
WHERE player_id IN (76375, 406) AND season_type = 'Regular Season'
ORDER BY player_id;

-- @H08
-- Not tracked: steals start in 1973-74; Russell's last season is 1968-69.
-- key: player_name
-- numbers:
-- null: steals
SELECT c.player_id, c.player_name, c.first_season, c.last_season, c.steals,
  a.stat, a.first_season AS first_season_tracked
FROM semantic.player_career_stats c, semantic.stat_availability a
WHERE c.player_id = 78049 AND c.season_type = 'Regular Season' AND a.stat = 'stl';

-- @H09
-- Not tracked: plus-minus starts in 1996-97.
-- key: player_name
-- numbers:
-- null: plus_minus
SELECT s.player_id, s.player_name, s.season, s.games_played, s.plus_minus,
  a.stat, a.first_season AS first_season_tracked
FROM semantic.player_season_stats s, semantic.stat_availability a
WHERE s.player_id = 893 AND s.season = '1991-92' AND s.season_type = 'Regular Season'
  AND a.stat = 'plus_minus';

-- @H10
-- Not tracked: blocks start in 1973-74.
-- key: player_name
-- numbers:
-- null: blocks
SELECT s.player_id, s.player_name, s.season, s.games_played, s.blocks,
  a.stat, a.first_season AS first_season_tracked
FROM semantic.player_season_stats s, semantic.stat_availability a
WHERE s.player_id = 78497 AND s.season = '1965-66' AND s.season_type = 'Regular Season'
  AND a.stat = 'blk';

-- ============================== Multi-turn ==============================

-- @M01.1
-- Same question as Q13.
-- key: player_name
-- numbers: points_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, points, points_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND points_per_game IS NOT NULL
), top AS (SELECT MAX(points_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.points / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY points_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, points, points_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @M01.2
-- key: player_name
-- numbers: assists_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, assists, assists_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND assists_per_game IS NOT NULL
), top AS (SELECT MAX(assists_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.assists / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY assists_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, assists, assists_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @M02.1
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id = 203999 AND season = '2024-25' AND season_type = 'Regular Season';

-- @M02.2
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id = 203999 AND season = '2024-25' AND season_type = 'Playoffs';

-- @M03.1
-- key: player_name
-- numbers: three_point_pct
SELECT player_id, player_name, season_type, threes_made, threes_attempted, three_point_pct
FROM semantic.player_career_stats
WHERE player_id IN (201939, 202691) AND season_type = 'Regular Season'
ORDER BY player_id;

-- @M03.2
-- Each player's last 3 regular seasons, one row per season (the compare tool's
-- last_n_seasons scope); the pooled 3-season percentage is context.
-- key: player_name, season
-- numbers: three_point_pct
WITH n AS (
  SELECT player_id, player_name, season, threes_made, threes_attempted, three_point_pct,
    ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season_start DESC) AS season_number
  FROM semantic.player_season_stats
  WHERE player_id IN (201939, 202691) AND season_type = 'Regular Season'
)
SELECT player_id, player_name, season, season_number, threes_made, threes_attempted,
  three_point_pct,
  SUM(threes_made) OVER (PARTITION BY player_id) / SUM(threes_attempted) OVER (PARTITION BY player_id)
    AS pooled_three_point_pct
FROM n WHERE season_number <= 3
ORDER BY player_id, season;

-- @M04.1
-- key: team_name
-- numbers: wins, losses
-- ordered: true
-- ties: rank by conference rank; ties list by team_id
WITH r AS (
  SELECT team_id, team_name, conference, conference_rank, wins, losses, win_pct,
    RANK() OVER (ORDER BY conference_rank NULLS LAST, win_pct DESC, wins DESC) AS rank
  FROM semantic.team_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND conference = 'West'
)
SELECT rank, team_id, team_name, conference, conference_rank, wins, losses, win_pct FROM r
WHERE rank <= 1 ORDER BY rank, team_id;

-- @M04.2
-- key: team_name
-- numbers: net_rating
SELECT team_id, team_name, season, season_type, net_rating
FROM semantic.team_season_stats
WHERE team_id = 1610612760 AND season = '2025-26' AND season_type = 'Regular Season';

-- @M05.1
-- key: player_name
-- numbers:
SELECT player_id, player_name, season, team_name
FROM semantic.awards
WHERE award = 'NBA Most Valuable Player' AND season = '2024-25'
ORDER BY player_id;

-- @M05.2
-- key: player_name
-- numbers: awards=mvp_awards
SELECT player_id, player_name, COUNT(*) AS awards, MIN(season) AS first_season,
  MAX(season) AS last_season
FROM semantic.awards
WHERE award = 'NBA Most Valuable Player' AND player_id = 1628983
GROUP BY player_id, player_name;

-- @M06.1
-- key: team_name
-- numbers: team_points_per_game
SELECT team_id, team_name, season, season_type, team_points_per_game
FROM semantic.team_season_stats
WHERE team_id = 1610612738 AND season = '2025-26' AND season_type = 'Regular Season';

-- @M06.2
-- key: team_name
-- numbers: defensive_rating
SELECT team_id, team_name, season, season_type, defensive_rating
FROM semantic.team_season_stats
WHERE team_id = 1610612738 AND season = '2025-26' AND season_type = 'Regular Season';

-- @M06.3
-- Required: the 2024-25 rating (the gold tool call); the 2025-26 value is turn 2's.
-- key: team_name, season
-- numbers: defensive_rating
SELECT team_id, team_name, season, season_type, defensive_rating
FROM semantic.team_season_stats
WHERE team_id = 1610612738 AND season = '2024-25' AND season_type = 'Regular Season';

-- @M07.1
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id = 1641705 AND season = '2023-24' AND season_type = 'Regular Season';

-- @M07.2
-- key: player_name
-- numbers: @stat_line
SELECT player_id, player_name, season, season_type, games_played, minutes_per_game,
  points_per_game, rebounds_per_game, assists_per_game, steals_per_game, blocks_per_game,
  field_goal_pct, three_point_pct, free_throw_pct
FROM semantic.player_season_stats
WHERE player_id = 1641705 AND season = '2024-25' AND season_type = 'Regular Season';

-- @M07.3
-- key: season
-- numbers: blocks_per_game
-- ordered: true
SELECT player_id, player_name, season, games_played, blocks, blocks_per_game
FROM semantic.player_season_stats
WHERE player_id = 1641705 AND season_type = 'Regular Season'
  AND season BETWEEN '2023-24' AND '2024-25'
ORDER BY season;

-- @M08.1
-- key: player_name
-- numbers: rebounds_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, rebounds, rebounds_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2025-26' AND season_type = 'Regular Season' AND rebounds_per_game IS NOT NULL
), top AS (SELECT MAX(rebounds_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.rebounds / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY rebounds_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, rebounds, rebounds_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @M08.2
-- key: player_name
-- numbers: rebounds_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH s AS (
  SELECT player_id, player_name, team_name, gp, team_gp, rebounds, rebounds_per_game,
    CEIL(0.70 * team_gp) AS min_gp
  FROM semantic.player_season_stats
  WHERE season = '2024-25' AND season_type = 'Regular Season' AND rebounds_per_game IS NOT NULL
), top AS (SELECT MAX(rebounds_per_game) AS best FROM s WHERE gp >= min_gp),
q AS (SELECT s.* FROM s, top WHERE s.gp >= s.min_gp OR s.rebounds / s.min_gp > top.best),
r AS (SELECT *, RANK() OVER (ORDER BY rebounds_per_game DESC) AS rank FROM q)
SELECT rank, player_id, player_name, team_name, gp, min_gp, rebounds, rebounds_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @M08.3
-- per_game_leader_playoffs: 70% of the team's playoff games, no "would still lead" clause.
-- key: player_name
-- numbers: rebounds_per_game
-- ordered: true
-- ties: every player tied for the last listed rank is included; ties list by player_id
WITH r AS (
  SELECT player_id, player_name, team_name, gp, team_gp, rebounds, rebounds_per_game,
    CEIL(0.70 * team_gp) AS min_gp, RANK() OVER (ORDER BY rebounds_per_game DESC) AS rank
  FROM semantic.player_season_stats
  WHERE season = '2024-25' AND season_type = 'Playoffs' AND rebounds_per_game IS NOT NULL
    AND gp >= CEIL(0.70 * team_gp)
)
SELECT rank, player_id, player_name, team_name, gp, min_gp, rebounds, rebounds_per_game
FROM r WHERE rank <= 1 ORDER BY rank, player_id;

-- @M09.1
-- key: player_name
-- numbers: points_per_game
SELECT player_id, player_name, season, games_played, points_per_game
FROM semantic.player_season_stats
WHERE player_id IN (203999, 203954) AND season = '2025-26' AND season_type = 'Regular Season'
ORDER BY player_id;

-- @M09.2
-- key: player_name
-- numbers: rebounds_per_game
SELECT player_id, player_name, season, games_played, rebounds_per_game
FROM semantic.player_season_stats
WHERE player_id IN (203999, 203954) AND season = '2025-26' AND season_type = 'Regular Season'
ORDER BY player_id;

-- @M09.3
-- key: player_name
-- numbers: games_played
SELECT player_id, player_name, season, games_played
FROM semantic.player_season_stats
WHERE player_id IN (203999, 203954) AND season = '2025-26' AND season_type = 'Regular Season'
ORDER BY player_id;

-- @M10.1
-- key: player_name
-- numbers: points, rebounds, assists, games_played
SELECT player_id, player_name, season_type, first_season, last_season, points, rebounds,
  assists, games_played
FROM semantic.player_career_stats
WHERE player_id = 2544 AND season_type = 'Playoffs';

-- @M10.2
-- key: player_name
-- numbers: points, rebounds, assists, games_played
SELECT player_id, player_name, season_type, first_season, last_season, points, rebounds,
  assists, games_played
FROM semantic.player_career_stats
WHERE player_id IN (2544, 201142) AND season_type = 'Playoffs'
ORDER BY player_id;

-- @M10.3
-- Clarify: "he" may be LeBron James or Kevin Durant (owner rule 0005).
-- key: player_name
-- numbers:
SELECT player_id, name AS player_name, from_year, to_year
FROM semantic.players WHERE player_id IN (2544, 201142) ORDER BY player_id;
