-- NBA.com's own career totals. Used only to check careers summed from player_season (task 1.20).
with src as (
    select *, 'Regular Season' as season_type
    from {{ source('landing', 'playercareerstats__careertotalsregularseason') }}
    union all by name
    select *, 'Playoffs' as season_type
    from {{ source('landing', 'playercareerstats__careertotalspostseason') }}
)
select
    {{ int_('PLAYER_ID') }} as player_id,
    season_type,
    {{ int_('GP') }} as gp, {{ num_('MIN') }} as minutes,
    {{ int_('FGM') }} as fgm, {{ int_('FGA') }} as fga,
    {{ int_('FG3M') }} as fg3m, {{ int_('FG3A') }} as fg3a,
    {{ int_('FTM') }} as ftm, {{ int_('FTA') }} as fta,
    {{ int_('REB') }} as reb, {{ int_('AST') }} as ast, {{ int_('STL') }} as stl,
    {{ int_('BLK') }} as blk, {{ int_('TOV') }} as tov, {{ int_('PTS') }} as pts
from src
where PLAYER_ID is not null
{{ latest_file_per('PLAYER_ID') }}
