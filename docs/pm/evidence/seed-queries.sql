-- T-SEEDS: one hand-written DuckDB query per Stats/Mixed seed, on semantic views only.
-- Conventions: this season = '2025-26' Regular Season; last season = '2024-25'; the pinned eval
-- snapshot ends 2026-04-12 (last RS game), so "last game / last night" use game_date <= '2026-04-12'.
-- dev.duckdb also holds the 2026 postseason, so queries that could see it add explicit filters.
-- Per-game leader qualification (simplified): games_played >= 0.7 * team_gp; Q13 shows the full rule.
-- Block format: "-- @<id> <split> | question", then the SQL, ended by a line with only ";".
-- This is an answerability check only; values are not compared to gold or to NBA.com.

-- @Q01 d | How many points per game is Shai Gilgeous-Alexander averaging this season?
SELECT player_name, season, games_played, points_per_game FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'shai gilgeous%' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q02 d | What are Nikola Jokic's averages this season?
SELECT player_name, games_played, points_per_game, rebounds_per_game, assists_per_game, steals_per_game,
  blocks_per_game, field_goal_pct, three_point_pct, free_throw_pct, minutes_per_game
FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'nikola joki%' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q03 d | How many triple-doubles does Jokic have this season?
SELECT player_name, games_played, triple_doubles FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'nikola joki%' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q04 d | What is Victor Wembanyama's blocks per game this season?
SELECT player_name, games_played, blocks_per_game FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'victor wembanyama' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q05 d | What are Cooper Flagg's rookie stats?
SELECT player_name, season, is_rookie_season, games_played, points_per_game, rebounds_per_game,
  assists_per_game, steals_per_game, blocks_per_game, field_goal_pct, three_point_pct
FROM semantic.player_season_stats
WHERE lower(player_name) = 'cooper flagg' AND is_rookie_season AND season_type = 'Regular Season'
;
-- @Q06 d | How many 3-pointers has Stephen Curry made this season?
SELECT player_name, games_played, threes_made FROM semantic.player_season_stats
WHERE lower(player_name) = 'stephen curry' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q07 h | What is LeBron James averaging this season?
SELECT player_name, games_played, points_per_game, rebounds_per_game, assists_per_game, steals_per_game,
  blocks_per_game, field_goal_pct, three_point_pct, free_throw_pct, minutes_per_game
FROM semantic.player_season_stats
WHERE lower(player_name) = 'lebron james' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q08 h | What is Luka Doncic's field goal percentage with the Lakers?
-- Team-scoped question: reads the stint view (the Lakers stint row), not a SUM of stints.
SELECT player_name, season, team_name, games_played, field_goals_made, field_goal_pct
FROM semantic.player_stint_stats
WHERE lower(player_name) LIKE 'luka don%' AND team_name LIKE '%Lakers' AND season_type = 'Regular Season'
ORDER BY season_start
;
-- @Q09 d | How many minutes per game does Anthony Edwards play?
SELECT player_name, games_played, minutes_per_game FROM semantic.player_season_stats
WHERE lower(player_name) = 'anthony edwards' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q10 h | What is Giannis Antetokounmpo's free throw percentage this season?
SELECT player_name, games_played, free_throws_made, free_throw_pct FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'giannis%' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q11 d | How many games has Jayson Tatum played this season?
SELECT player_name, games_played FROM semantic.player_season_stats
WHERE lower(player_name) = 'jayson tatum' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q12 d | What were Shai Gilgeous-Alexander's playoff stats last season?
SELECT player_name, season, season_type, games_played, points_per_game, rebounds_per_game,
  assists_per_game, steals_per_game, blocks_per_game, field_goal_pct, three_point_pct
FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'shai gilgeous%' AND season = '2024-25' AND season_type = 'Playoffs'
;
-- @Q13 d | Who leads the NBA in scoring this season?
-- Full per-game rule: >= 70% of team games, or fewer if total / that minimum would still lead.
WITH s AS (
  SELECT player_name, team_name, points, games_played, points_per_game, CEIL(0.7 * team_gp) AS min_gp
  FROM semantic.player_season_stats WHERE season = '2025-26' AND season_type = 'Regular Season'
), q AS (SELECT MAX(points_per_game) AS top FROM s WHERE games_played >= min_gp)
SELECT s.player_name, s.team_name, s.games_played, s.points_per_game
FROM s, q WHERE s.games_played >= s.min_gp OR s.points * 1.0 / s.min_gp > q.top
ORDER BY s.points_per_game DESC LIMIT 5
;
-- @Q14 d | Who are the top 5 rebounders in the NBA this season?
SELECT player_name, team_name, games_played, rebounds_per_game, rebounds FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' AND games_played >= 0.7 * team_gp
ORDER BY rebounds_per_game DESC LIMIT 5
;
-- @Q15 h | Who leads the league in assists per game?
SELECT player_name, team_name, games_played, assists_per_game FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' AND games_played >= 0.7 * team_gp
ORDER BY assists_per_game DESC LIMIT 5
;
-- @Q16 h | Who has the most blocks this season?
SELECT player_name, team_name, games_played, blocks FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season'
ORDER BY blocks DESC LIMIT 5
;
-- @Q17 d | Who has the highest 3-point percentage (qualified) this season?
-- Qualification (registry fg3_pct_leader): at least 82 made threes.
SELECT player_name, team_name, threes_made, threes_attempted, three_point_pct FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' AND threes_made >= 82
ORDER BY three_point_pct DESC LIMIT 5
;
-- @Q18 h | Which player has the most double-doubles this season?
SELECT player_name, team_name, games_played, double_doubles FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season'
ORDER BY double_doubles DESC LIMIT 5
;
-- @Q19 d | Who leads the NBA in steals per game?
SELECT player_name, team_name, games_played, steals_per_game FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' AND games_played >= 0.7 * team_gp
ORDER BY steals_per_game DESC LIMIT 5
;
-- @Q20 d | Which rookie is scoring the most this season?
SELECT player_name, team_name, games_played, points_per_game FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' AND is_rookie_season AND games_played >= 0.7 * team_gp
ORDER BY points_per_game DESC LIMIT 5
;
-- @Q21 d | Who has the most 40-point games this season?
SELECT player_name, team_name, games_played, forty_point_games FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season'
ORDER BY forty_point_games DESC LIMIT 5
;
-- @Q22 h | Who leads the league in plus-minus?
SELECT player_name, team_name, games_played, plus_minus FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season'
ORDER BY plus_minus DESC LIMIT 5
;
-- @Q23 d | Who is better statistically this season: Jokic or Gilgeous-Alexander?
SELECT player_name, games_played, points_per_game, rebounds_per_game, assists_per_game, steals_per_game,
  blocks_per_game, true_shooting_pct, plus_minus
FROM semantic.player_season_stats
WHERE (lower(player_name) LIKE 'nikola joki%' OR lower(player_name) LIKE 'shai gilgeous%')
  AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q24 d | Compare LeBron James and Michael Jordan career playoff stats.
SELECT player_name, season_type, games_played, points_per_game, rebounds_per_game, assists_per_game,
  steals_per_game, blocks_per_game, field_goal_pct, three_point_pct
FROM semantic.player_career_stats
WHERE lower(player_name) IN ('lebron james', 'michael jordan') AND season_type = 'Playoffs'
;
-- @Q25 d | Compare Curry and Klay Thompson career 3-point percentage.
SELECT player_name, threes_made, threes_attempted, three_point_pct FROM semantic.player_career_stats
WHERE lower(player_name) IN ('stephen curry', 'klay thompson') AND season_type = 'Regular Season'
;
-- @Q26 h | Who has more career rebounds, Wilt Chamberlain or Bill Russell?
SELECT player_name, games_played, rebounds FROM semantic.player_career_stats
WHERE lower(player_name) IN ('wilt chamberlain', 'bill russell') AND season_type = 'Regular Season'
;
-- @Q27 d | How do Wembanyama's first two seasons compare to Tim Duncan's?
WITH r AS (
  SELECT player_name, season, games_played, points, rebounds, assists, blocks,
    ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season_start) AS n
  FROM semantic.player_season_stats
  WHERE lower(player_name) IN ('victor wembanyama', 'tim duncan') AND season_type = 'Regular Season'
)
SELECT player_name, MIN(season) AS from_season, MAX(season) AS to_season, SUM(games_played) AS gp,
  SUM(points) * 1.0 / SUM(games_played) AS ppg, SUM(rebounds) * 1.0 / SUM(games_played) AS rpg,
  SUM(assists) * 1.0 / SUM(games_played) AS apg, SUM(blocks) * 1.0 / SUM(games_played) AS bpg
FROM r WHERE n <= 2 GROUP BY player_name
;
-- @Q28 d | Compare Anthony Edwards and Ja Morant scoring this season.
SELECT player_name, games_played, points, points_per_game FROM semantic.player_season_stats
WHERE lower(player_name) IN ('anthony edwards', 'ja morant') AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q29 h | Kobe Bryant vs LeBron James: career points and championships
SELECT player_name, points, player_championships FROM semantic.player_career_stats
WHERE lower(player_name) IN ('kobe bryant', 'lebron james') AND season_type = 'Regular Season'
;
-- @Q30 h | Which team has a better defensive rating, the Celtics or the Thunder?
SELECT team_name, season, defensive_rating FROM semantic.team_season_stats
WHERE (team_name LIKE '%Celtics' OR team_name LIKE '%Thunder') AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q31 d | Who is the NBA's all-time leading scorer?
SELECT player_name, points, games_played FROM semantic.player_career_stats
WHERE season_type = 'Regular Season' ORDER BY points DESC LIMIT 3
;
-- @Q32 h | Who has the most career assists in NBA history?
SELECT player_name, assists, games_played FROM semantic.player_career_stats
WHERE season_type = 'Regular Season' ORDER BY assists DESC LIMIT 3
;
-- @Q33 d | Who has the most 3-pointers made in NBA history?
SELECT player_name, threes_made, games_played FROM semantic.player_career_stats
WHERE season_type = 'Regular Season' ORDER BY threes_made DESC LIMIT 3
;
-- @Q34 d | What is the most points scored by a player in a single game?
SELECT record, player_name, value, game_date, season FROM semantic.records
WHERE stat = 'pts' AND record_kind = 'single_game' ORDER BY value DESC LIMIT 3
;
-- @Q35 h | Who has the most career triple-doubles?
SELECT player_name, triple_doubles, games_played FROM semantic.player_career_stats
WHERE season_type = 'Regular Season' ORDER BY triple_doubles DESC LIMIT 5
;
-- @Q36 d | How many career points does LeBron James have?
SELECT player_name, points FROM semantic.player_career_stats
WHERE lower(player_name) = 'lebron james' AND season_type = 'Regular Season'
;
-- @Q37 h | Who has the highest career points per game?
-- Qualification (registry career_per_game): 400 games and 10,000 points.
SELECT player_name, games_played, points, points_per_game FROM semantic.player_career_stats
WHERE season_type = 'Regular Season' AND games_played >= 400 AND points >= 10000
ORDER BY points_per_game DESC LIMIT 5
;
-- @Q38 h | Who has the most career blocks?
SELECT player_name, blocks, games_played FROM semantic.player_career_stats
WHERE season_type = 'Regular Season' ORDER BY blocks DESC LIMIT 5
;
-- @Q39 d | Which team has won the most NBA championships?
SELECT f.current_name, COUNT(*) AS titles FROM semantic.team_titles t
JOIN semantic.franchises f ON f.franchise_id = t.franchise_id
GROUP BY f.current_name ORDER BY titles DESC LIMIT 3
;
-- @Q40 d | What is the best regular-season record of all time?
SELECT team_name, season, wins, losses, win_pct FROM semantic.team_season_stats
WHERE season_type = 'Regular Season' ORDER BY win_pct DESC LIMIT 3
;
-- @Q41 d | Who has played the most games in NBA history?
SELECT player_name, games_played FROM semantic.player_career_stats
WHERE season_type = 'Regular Season' ORDER BY games_played DESC LIMIT 3
;
-- @Q42 d | What is the most 3-pointers made in one game?
SELECT record, player_name, value, game_date, season FROM semantic.records
WHERE stat = 'fg3m' AND record_kind = 'single_game' ORDER BY value DESC LIMIT 3
;
-- @Q43 d | What are the current NBA standings in the Western Conference?
SELECT conference_rank, team_name, wins, losses, win_pct FROM semantic.team_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' AND conference = 'West'
ORDER BY conference_rank
;
-- @Q44 d | Which team has the best record this season?
SELECT team_name, wins, losses, win_pct FROM semantic.team_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' ORDER BY win_pct DESC LIMIT 3
;
-- @Q45 d | Which team scores the most points per game?
SELECT team_name, team_points_per_game FROM semantic.team_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' ORDER BY team_points_per_game DESC LIMIT 3
;
-- @Q46 d | What is the Lakers' record at home this season?
SELECT team_name, home_wins, home_losses FROM semantic.team_season_stats
WHERE team_name LIKE '%Lakers' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q47 h | Which team has the best net rating?
SELECT team_name, net_rating FROM semantic.team_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' ORDER BY net_rating DESC LIMIT 3
;
-- @Q48 d | Who is the Warriors' leading scorer this season?
-- Team-scoped leader: reads the stint view (that team's stint row), per CLAUDE.md.
SELECT player_name, team_name, games_played, points_per_game FROM semantic.player_stint_stats
WHERE team_name LIKE '%Warriors' AND season = '2025-26' AND season_type = 'Regular Season'
  AND games_played >= 0.7 * team_gp
ORDER BY points_per_game DESC LIMIT 3
;
-- @Q49 d | Which team plays at the fastest pace?
SELECT team_name, pace FROM semantic.team_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' ORDER BY pace DESC LIMIT 3
;
-- @Q50 h | What is the Knicks' longest winning streak this season?
WITH k AS (SELECT team_id FROM semantic.teams WHERE name = 'Knicks' AND is_current),
g AS (
  SELECT x.game_date, CASE WHEN x.winner_team_id = k.team_id THEN 1 ELSE 0 END AS w
  FROM semantic.games x, k
  WHERE x.season = '2025-26' AND x.season_type = 'Regular Season'
    AND (x.home_team_id = k.team_id OR x.away_team_id = k.team_id)
), r AS (
  SELECT game_date, w, SUM(1 - w) OVER (ORDER BY game_date ROWS UNBOUNDED PRECEDING) AS losses_before
  FROM g
)
SELECT SUM(w) AS streak, MIN(game_date) AS first_win, MAX(game_date) AS last_win
FROM r WHERE w = 1 GROUP BY losses_before ORDER BY streak DESC LIMIT 1
;
-- @Q51 h | Who won the last game between the Celtics and the Knicks?
-- Cutoff 2026-04-12 = pinned eval snapshot (no playoffs).
SELECT game_date, season_type, home_team_name, home_pts, away_team_name, away_pts FROM semantic.games
WHERE game_date <= '2026-04-12'
  AND ((home_team_name LIKE '%Celtics' AND away_team_name LIKE '%Knicks')
    OR (home_team_name LIKE '%Knicks' AND away_team_name LIKE '%Celtics'))
ORDER BY game_date DESC LIMIT 1
;
-- @Q52 d | How many points did Jokic score in his last game?
SELECT player_name, game_date, matchup, pts FROM semantic.player_game_log
WHERE lower(player_name) LIKE 'nikola joki%' AND game_date <= '2026-04-12'
ORDER BY game_date DESC LIMIT 1
;
-- @Q53 d | What was the final score of the last NBA Finals game?
-- Finals = playoff game between that season's champion and its Finals opponent (team_titles).
SELECT g.game_date, g.season, g.home_team_name, g.home_pts, g.away_team_name, g.away_pts
FROM semantic.games g JOIN semantic.team_titles t ON g.season = t.season
WHERE g.season_type = 'Playoffs' AND g.game_date <= '2026-04-12'
  AND ((g.home_team_id = t.team_id AND g.away_team_id = t.opponent_team_id)
    OR (g.away_team_id = t.team_id AND g.home_team_id = t.opponent_team_id))
ORDER BY g.game_date DESC LIMIT 1
;
-- @Q54 h | Who had the highest-scoring game this season?
SELECT player_name, pts, game_date, matchup FROM semantic.player_game_log
WHERE season = '2025-26' AND season_type = 'Regular Season' ORDER BY pts DESC LIMIT 3
;
-- @Q55 d | What were the box score leaders in last night's games?
-- Snapshot as_of_date = 2026-04-13, so last night = 2026-04-12. Top scorer per game.
SELECT game_id, player_name, matchup, pts, reb, ast FROM (
  SELECT game_id, player_name, matchup, pts, reb, ast,
    ROW_NUMBER() OVER (PARTITION BY game_id ORDER BY pts DESC) AS rn
  FROM semantic.player_game_log WHERE game_date = '2026-04-12'
) WHERE rn = 1 ORDER BY game_id
;
-- @Q56 d | How many points did Curry score in his last 5 games?
SELECT game_date, matchup, pts FROM semantic.player_game_log
WHERE lower(player_name) = 'stephen curry' AND game_date <= '2026-04-12'
ORDER BY game_date DESC LIMIT 5
;
-- @Q57 d | Which games this season went to overtime?
SELECT game_date, home_team_name, home_pts, away_team_name, away_pts, periods FROM semantic.games
WHERE season = '2025-26' AND season_type = 'Regular Season' AND overtime ORDER BY game_date
;
-- @Q58 d | What was the largest margin of victory this season?
SELECT game_date, home_team_name, home_pts, away_team_name, away_pts, margin FROM semantic.games
WHERE season = '2025-26' AND season_type = 'Regular Season' ORDER BY margin DESC LIMIT 3
;
-- @Q59 h | How has the league-average 3-point attempt rate changed since 2010?
SELECT season, league_three_point_attempt_rate FROM semantic.league_season_stats
WHERE season_type = 'Regular Season' AND season_start >= 2010 ORDER BY season_start
;
-- @Q60 d | How has Wembanyama's 3-point percentage changed each season?
SELECT season, threes_made, threes_attempted, three_point_pct FROM semantic.player_season_stats
WHERE lower(player_name) = 'victor wembanyama' AND season_type = 'Regular Season' ORDER BY season_start
;
-- @Q61 h | How has LeBron's scoring changed over his career?
SELECT season, team_name, games_played, points_per_game FROM semantic.player_season_stats
WHERE lower(player_name) = 'lebron james' AND season_type = 'Regular Season' ORDER BY season_start
;
-- @Q62 d | Is league-wide scoring higher now than in the 1990s?
SELECT CASE WHEN season_start BETWEEN 1990 AND 1999 THEN '1990s' ELSE season END AS period,
  AVG(league_points_per_game) AS avg_ppg, COUNT(*) AS seasons
FROM semantic.league_season_stats
WHERE season_type = 'Regular Season' AND (season_start BETWEEN 1990 AND 1999 OR season = '2025-26')
GROUP BY 1
;
-- @Q63 d | How have the Thunder's wins changed over the last 5 seasons?
SELECT season, team_name, wins, losses FROM semantic.team_season_stats
WHERE team_name LIKE '%Thunder' AND season_type = 'Regular Season' AND season_start >= 2021
ORDER BY season_start
;
-- @Q64 d | Has Jokic's assist average gone up every season?
SELECT season, games_played, assists_per_game,
  assists_per_game - LAG(assists_per_game) OVER (ORDER BY season_start) AS change
FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'nikola joki%' AND season_type = 'Regular Season' ORDER BY season_start
;
-- @Q71 h | Who has the highest true shooting percentage this season, and what does it mean?
-- Stats half only; the definition comes from the glossary (knowledge path, not a view).
-- Qualification (registry ts_pct_leader): 70% of team games and 300 made field goals.
SELECT player_name, team_name, games_played, field_goals_made, true_shooting_pct FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' AND games_played >= 0.7 * team_gp
  AND field_goals_made >= 300
ORDER BY true_shooting_pct DESC LIMIT 5
;
-- @Q72 d | Is Jokic's usage rate high for a center, and what is usage rate?
-- Stats half only; the definition is glossary text. Centers = players.position starts with Center.
-- (A UNION ALL form is rejected by a guard bug when it has no LIMIT: see DEF in T-SEEDS.md.)
WITH j AS (
  SELECT usage_rate AS jokic_usage FROM semantic.player_season_stats
  WHERE lower(player_name) LIKE 'nikola joki%' AND season = '2025-26' AND season_type = 'Regular Season'
), c AS (
  SELECT AVG(s.usage_rate) AS centers_avg_usage, COUNT(*) AS n_centers
  FROM semantic.player_season_stats s JOIN semantic.players p ON p.player_id = s.player_id
  WHERE s.season = '2025-26' AND s.season_type = 'Regular Season' AND p.position LIKE 'Center%'
    AND s.minutes >= 500
)
SELECT j.jokic_usage, c.centers_avg_usage, c.n_centers FROM j, c
;
-- @Q73 d | Where does Curry take most of his shots from?
SELECT zone, COUNT(*) AS attempts, SUM(CAST(made AS INT)) AS makes
FROM semantic.shots
WHERE lower(player_name) = 'stephen curry' AND season = '2025-26' AND season_type = 'Regular Season'
GROUP BY zone ORDER BY attempts DESC
;
-- @Q74 d | What is Giannis's field goal percentage in the restricted area?
SELECT player_name, season, restricted_area_fg_pct FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'giannis%' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q75 d | Which player makes the most corner 3s?
SELECT player_name, team_name, corner_threes_made FROM semantic.player_season_stats
WHERE season = '2025-26' AND season_type = 'Regular Season' ORDER BY corner_threes_made DESC LIMIT 5
;
-- @Q76 h | What is Luka's percentage on step-back 3s?
SELECT player_name, season, step_back_three_pct FROM semantic.player_season_stats
WHERE lower(player_name) LIKE 'luka don%' AND season = '2025-26' AND season_type = 'Regular Season'
;
-- @Q77 h | Who won MVP last season, and what were his stats?
SELECT a.player_name, a.season, s.games_played, s.points_per_game, s.rebounds_per_game, s.assists_per_game
FROM semantic.awards a JOIN semantic.player_season_stats s
  ON s.player_id = a.player_id AND s.season = a.season AND s.season_type = 'Regular Season'
WHERE a.award = 'NBA Most Valuable Player' AND a.season = '2024-25'
;
-- @Q78 d | Who has won the most MVP awards?
-- season <= 2024-25 keeps the answer at the pinned snapshot (dev also holds the 2025-26 award).
SELECT player_name, COUNT(*) AS mvps FROM semantic.awards
WHERE award = 'NBA Most Valuable Player' AND season_start <= 2024
GROUP BY player_id, player_name ORDER BY mvps DESC LIMIT 3
;
-- @Q79 d | Who won Rookie of the Year in 2024?
SELECT player_name, season FROM semantic.awards
WHERE award = 'NBA Rookie of the Year' AND season = '2023-24'
;
-- @Q80 d | How many All-Star selections does LeBron James have?
SELECT player_name, all_star_selections FROM semantic.player_career_stats
WHERE lower(player_name) = 'lebron james' AND season_type = 'Regular Season'
;
-- @Q85 d | How many 3-pointers did Wilt Chamberlain make?
-- Expected NULL (3-point line introduced 1979-80); stat_availability marks fg3m first tracked 1979-80.
SELECT player_name, threes_made, threes_attempted FROM semantic.player_career_stats
WHERE lower(player_name) = 'wilt chamberlain' AND season_type = 'Regular Season'
;
