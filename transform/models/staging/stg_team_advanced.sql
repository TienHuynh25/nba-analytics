select
    {{ int_('TEAM_ID') }} as team_id,
    {{ param_('Season') }} as season,
    {{ param_('SeasonType') }} as season_type,
    {{ int_('GP') }} as gp,
    {{ num_('OFF_RATING') }} as off_rating,
    {{ num_('DEF_RATING') }} as def_rating,
    {{ num_('NET_RATING') }} as net_rating,
    {{ num_('PACE') }} as pace,
    {{ num_('TS_PCT') }} as ts_pct_published,
    {{ num_('POSS') }} as poss
from {{ source('landing', 'leaguedashteamstats_adv__leaguedashteamstats') }}
where TEAM_ID is not null
{{ latest_file_per('_params') }}
