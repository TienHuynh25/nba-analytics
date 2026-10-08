-- NBA.com's published advanced stats. Usage rate is taken from here; TS% is recomputed by the
-- registry and this published value is only the check for task 3.2.
select
    {{ int_('PLAYER_ID') }} as player_id,
    {{ param_('Season') }} as season,
    {{ param_('SeasonType') }} as season_type,
    {{ int_('GP') }} as gp,
    {{ num_('USG_PCT') }} as usg_pct,
    {{ num_('TS_PCT') }} as ts_pct_published,
    {{ num_('EFG_PCT') }} as efg_pct_published,
    {{ num_('OFF_RATING') }} as off_rating,
    {{ num_('DEF_RATING') }} as def_rating,
    {{ num_('NET_RATING') }} as net_rating,
    {{ num_('PACE') }} as pace,
    {{ num_('PIE') }} as pie
from {{ source('landing', 'leaguedashplayerstats_adv__leaguedashplayerstats') }}
where PLAYER_ID is not null
{{ latest_file_per('_params') }}
