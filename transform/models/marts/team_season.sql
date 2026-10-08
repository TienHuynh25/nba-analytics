-- Team x season x season type (task 1.17). W-L and points come from games for every season type;
-- standings and advanced ratings join where NBA.com has them.
with g as (
    select game_id, season, season_start, season_type, home_team_id as team_id,
           case when not is_neutral then true end as home, home_pts as pts, away_pts as opp_pts
    from {{ ref('games') }}
    union all
    select game_id, season, season_start, season_type, away_team_id,
           case when not is_neutral then false end, away_pts, home_pts
    from {{ ref('games') }}
),
wl as (
    select
        team_id, season, season_start, season_type,
        count(*) as gp,
        count(*) filter (where pts > opp_pts) as wins,
        count(*) filter (where pts < opp_pts) as losses,
        count(*) filter (where home and pts > opp_pts) as home_wins,
        count(*) filter (where home and pts < opp_pts) as home_losses,
        count(*) filter (where home = false and pts > opp_pts) as road_wins,
        count(*) filter (where home = false and pts < opp_pts) as road_losses,
        count(*) filter (where home is null) as neutral_games,
        sum(pts) as pts,
        sum(opp_pts) as opp_pts
    from g
    group by all
),
box as (
    -- Team box-score totals (for league-wide rates such as 3-point attempt rate).
    select t.team_id, t.season, g.season_type,
           sum(t.fgm) as fgm, sum(t.fga) as fga, sum(t.fg3m) as fg3m, sum(t.fg3a) as fg3a,
           sum(t.ftm) as ftm, sum(t.fta) as fta, sum(t.reb) as reb, sum(t.ast) as ast,
           sum(t.tov) as tov
    from {{ ref('stg_team_game') }} t
    join {{ ref('games') }} g using (game_id)
    group by all
),
st as (
    select s.* from {{ ref('stg_standings') }} s
    join {{ ref('int_season_type_status') }} x
      on x.season = s.season and x.season_type = 'Regular Season' and x.included
)
select
    wl.team_id,
    wl.team_id as franchise_id,
    wl.season,
    wl.season_start,
    wl.season_type,
    wl.gp, wl.wins, wl.losses,
    wl.wins / nullif(wl.gp, 0) as win_pct,
    wl.home_wins, wl.home_losses, wl.road_wins, wl.road_losses, wl.neutral_games,
    wl.pts, wl.opp_pts,
    box.fgm, box.fga, box.fg3m, box.fg3a, box.ftm, box.fta, box.reb, box.ast, box.tov,
    case when wl.season_type = 'Regular Season' then st.conference end as conference,
    case when wl.season_type = 'Regular Season' then st.division end as division,
    case when wl.season_type = 'Regular Season'
         then coalesce(st.conference_rank, ty.conf_rank) end as conference_rank,
    case when wl.season_type = 'Regular Season' then st.league_rank end as league_rank,
    adv.off_rating,
    adv.def_rating,
    adv.net_rating,
    adv.pace
from wl
left join box
  on box.team_id = wl.team_id and box.season = wl.season and box.season_type = wl.season_type
left join st on st.team_id = wl.team_id and st.season = wl.season
left join {{ ref('stg_team_year') }} ty on ty.team_id = wl.team_id and ty.season = wl.season
left join {{ ref('stg_team_advanced') }} adv
  on adv.team_id = wl.team_id and adv.season = wl.season and adv.season_type = wl.season_type
