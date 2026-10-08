-- Season rows from PlayerCareerStats: one per team a player played for, plus the source's own
-- total row (TEAM_ID = 0, 'TOT') for traded players. The latest response per player wins as a whole.
with src as (
    select *, 'Regular Season' as season_type
    from {{ source('landing', 'playercareerstats__seasontotalsregularseason') }}
    union all by name
    select *, 'Playoffs' as season_type
    from {{ source('landing', 'playercareerstats__seasontotalspostseason') }}
),
latest as (
    select * from src
    where PLAYER_ID is not null
    {{ latest_file_per('PLAYER_ID') }}
)
select
    {{ int_('PLAYER_ID') }} as player_id,
    SEASON_ID as season,
    {{ season_start('SEASON_ID') }} as season_start,
    season_type,
    {{ int_('TEAM_ID') }} as team_id,
    TEAM_ABBREVIATION as team_abbreviation,
    {{ int_('TEAM_ID') }} = 0 as is_total_row,
    {{ int_('PLAYER_AGE') }} as player_age,
    {{ int_('GP') }} as gp, {{ int_('GS') }} as gs, {{ num_('MIN') }} as minutes,
    {{ int_('FGM') }} as fgm, {{ int_('FGA') }} as fga,
    {{ int_('FG3M') }} as fg3m, {{ int_('FG3A') }} as fg3a,
    {{ int_('FTM') }} as ftm, {{ int_('FTA') }} as fta,
    {{ int_('OREB') }} as oreb, {{ int_('DREB') }} as dreb, {{ int_('REB') }} as reb,
    {{ int_('AST') }} as ast, {{ int_('STL') }} as stl, {{ int_('BLK') }} as blk,
    {{ int_('TOV') }} as tov, {{ int_('PF') }} as pf, {{ int_('PTS') }} as pts,
    cast(_fetched_at as timestamptz) as fetched_at
from latest
