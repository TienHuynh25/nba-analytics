-- One row per game (task 1.13). Dates are US Eastern as NBA.com reports them.
-- Periods: team minutes 240 = regulation; each overtime adds 25 (5 players x 5 minutes).
-- Division tiebreaker games of 1948-1957 (seed tiebreaker_games) carry season type 'Tiebreaker':
-- NBA.com's game log labels them regular season but its team records exclude them. Games that
-- were never played (2013-04-16 BOS-IND, cancelled) are dropped.
with t as (
    select g.* replace (
        case when tb.game_id is not null then 'Tiebreaker' else g.season_type end as season_type)
    from {{ ref('stg_team_game') }} g
    left join {{ ref('tiebreaker_games') }} tb using (game_id)
    where {{ as_of_date_filter('g.game_date') }}
      and not (g.wl is null and g.minutes = 0)
),
ranked as (
    -- Exactly one "vs." row marks the home team. Neutral-site games (both rows "@" or both "vs.")
    -- get a nominal home team (lower team_id) and is_neutral, as NBA.com standings keep a
    -- separate neutral record; they are excluded from home and road splits.
    select *,
           count(*) filter (where is_home) over (partition by game_id) as home_rows,
           row_number() over (partition by game_id order by is_home desc, team_id) as rn
    from t
),
paired as (
    select
        h.game_id,
        h.season,
        h.season_type,
        h.game_date,
        h.team_id as home_team_id,
        a.team_id as away_team_id,
        h.pts as home_pts,
        a.pts as away_pts,
        h.minutes as team_minutes,
        h.home_rows <> 1 as is_neutral
    from ranked h
    join ranked a on a.game_id = h.game_id and a.rn = 2
    where h.rn = 1
)
select
    game_id,
    season,
    {{ season_start('season') }} as season_start,
    season_type,
    game_date,
    home_team_id,
    away_team_id,
    home_pts,
    away_pts,
    case when home_pts > away_pts then home_team_id else away_team_id end as winner_team_id,
    abs(home_pts - away_pts) as margin,
    case when team_minutes >= 240 then 4 + cast(round((team_minutes - 240) / 25.0) as integer) end
        as periods,
    team_minutes > 240 as overtime,
    is_neutral,
    season_type = 'Cup Final' as is_cup_final
from paired
