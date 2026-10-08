select
    GAME_ID as game_id,
    {{ int_('GAME_EVENT_ID') }} as game_event_id,
    {{ param_('Season') }} as season,
    {{ season_type_from_game_id('GAME_ID') }} as season_type,
    strptime(GAME_DATE, '%Y%m%d')::date as game_date,
    {{ int_('PLAYER_ID') }} as player_id,
    {{ int_('TEAM_ID') }} as team_id,
    {{ int_('PERIOD') }} as period,
    {{ int_('MINUTES_REMAINING') }} as minutes_remaining,
    {{ int_('SECONDS_REMAINING') }} as seconds_remaining,
    ACTION_TYPE as action_type,
    SHOT_TYPE as shot_type,
    SHOT_ZONE_BASIC as zone,
    SHOT_ZONE_AREA as zone_area,
    SHOT_ZONE_RANGE as zone_range,
    {{ int_('SHOT_DISTANCE') }} as distance_ft,
    {{ int_('LOC_X') }} as x,
    {{ int_('LOC_Y') }} as y,
    {{ int_('SHOT_MADE_FLAG') }} = 1 as made
from {{ source('landing', 'shotchartdetail__shot_chart_detail') }}
where GAME_ID is not null
{{ latest_file_per('_params') }}
