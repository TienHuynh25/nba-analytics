-- Task 1.20: no team plays more regular-season games than its season's schedule length
-- (82 unless the season_schedule seed says otherwise: early seasons and shortened seasons).
-- Tiebreaker games have their own season type, so they are not counted here.
select ts.team_id, ts.season, ts.gp, coalesce(s.max_games, 82) as max_games
from {{ ref('team_season') }} ts
left join {{ ref('season_schedule') }} s on s.season_start = ts.season_start
where ts.season_type = 'Regular Season'
  and ts.gp > coalesce(s.max_games, 82)
