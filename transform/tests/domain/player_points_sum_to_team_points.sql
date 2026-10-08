-- Task 1.20: player points must sum to team points in every game. Mismatches are allowed only
-- where known_boxscore_gaps lists them (partial pre-1996-97 box scores and one 1998-99 source
-- error; see ingest/ENDPOINTS.md), and only with the same values, so any new gap fails.
with p as (
    select game_id, team_id, sum(pts) as player_pts
    from {{ ref('player_game') }}
    group by all
),
t as (
    select game_id, home_team_id as team_id, home_pts as team_pts from {{ ref('games') }}
    union all
    select game_id, away_team_id, away_pts from {{ ref('games') }}
),
mismatch as (
    select t.game_id, t.team_id, t.team_pts, coalesce(p.player_pts, 0) as player_pts
    from t left join p using (game_id, team_id)
    where t.team_pts is distinct from coalesce(p.player_pts, 0)
)
select m.*
from mismatch m
left join {{ ref('known_boxscore_gaps') }} k
  on k.game_id = m.game_id and k.team_id = m.team_id
 and k.team_pts = m.team_pts and k.player_pts = m.player_pts
where k.game_id is null
