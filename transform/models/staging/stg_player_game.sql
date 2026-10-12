-- One row per player per game. NULL stays NULL (untracked or missing), never 0.
-- The source lists 15 players under both teams in one game (e.g. Bob Cousy, BAL 0 pts and BOS 13
-- in 0025100113). The row kept is the one whose team box score reconciles with the team's points
-- when it is counted; then more points, more minutes, lower team_id. The choice is deterministic.
with rows_ as (
    select
        GAME_ID as game_id,
        {{ season_from_id('SEASON_ID') }} as season,
        {{ season_type_from_game_id('GAME_ID') }} as season_type,
        cast(GAME_DATE as date) as game_date,
        {{ int_('PLAYER_ID') }} as player_id,
        PLAYER_NAME as player_name,
        {{ int_('TEAM_ID') }} as team_id,
        MATCHUP as matchup,
        WL as wl,
        {{ int_('MIN') }} as minutes,
        {{ int_('FGM') }} as fgm, {{ int_('FGA') }} as fga,
        {{ int_('FG3M') }} as fg3m, {{ int_('FG3A') }} as fg3a,
        {{ int_('FTM') }} as ftm, {{ int_('FTA') }} as fta,
        {{ int_('OREB') }} as oreb, {{ int_('DREB') }} as dreb, {{ int_('REB') }} as reb,
        {{ int_('AST') }} as ast, {{ int_('STL') }} as stl, {{ int_('BLK') }} as blk,
        {{ int_('TOV') }} as tov, {{ int_('PF') }} as pf, {{ int_('PTS') }} as pts,
        {{ int_('PLUS_MINUS') }} as plus_minus,
        cast(_fetched_at as timestamptz) as fetched_at
    from {{ source('landing', 'leaguegamelog_p__leaguegamelog') }}
    where GAME_ID is not null
    {{ latest_per('GAME_ID, PLAYER_ID, TEAM_ID') }}
),
others as (
    -- Team points from rows that are not duplicated players.
    select r.game_id, r.team_id, sum(r.pts) as pts
    from rows_ r
    where (r.game_id, r.player_id) not in (
        select game_id, player_id from rows_ group by all having count(*) > 1)
    group by all
)
select r.*
from rows_ r
left join others o using (game_id, team_id)
left join {{ ref('stg_team_game') }} t using (game_id, team_id)
qualify row_number() over (
    partition by r.game_id, r.player_id
    order by (coalesce(o.pts, 0) + coalesce(r.pts, 0) = t.pts) desc nulls last,
             r.pts desc nulls last, r.minutes desc nulls last, r.team_id
) = 1
