-- One row per team per game. Season type comes from the game ID prefix, not the request, because
-- an IST request also returns ordinary regular-season (002) games.
select
    GAME_ID as game_id,
    {{ season_from_id('SEASON_ID') }} as season,
    {{ season_type_from_game_id('GAME_ID') }} as season_type,
    cast(GAME_DATE as date) as game_date,
    {{ int_('TEAM_ID') }} as team_id,
    TEAM_ABBREVIATION as team_abbreviation,
    TEAM_NAME as team_name,
    MATCHUP as matchup,
    MATCHUP like '% vs. %' as is_home,
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
from {{ source('landing', 'leaguegamelog_t__leaguegamelog') }}
where GAME_ID is not null
{{ latest_per('GAME_ID, TEAM_ID') }}
