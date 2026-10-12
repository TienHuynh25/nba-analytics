-- TeamYearByYearStats: regular-season W-L per franchise season, plus Finals result.
select
    {{ int_('TEAM_ID') }} as team_id,
    TEAM_CITY as city,
    TEAM_NAME as name,
    YEAR as season,
    {{ season_start('YEAR') }} as season_start,
    {{ int_('GP') }} as gp,
    {{ int_('WINS') }} as wins,
    {{ int_('LOSSES') }} as losses,
    {{ int_('CONF_RANK') }} as conf_rank,
    {{ int_('DIV_RANK') }} as div_rank,
    {{ int_('PO_WINS') }} as po_wins,
    {{ int_('PO_LOSSES') }} as po_losses,
    nullif(NBA_FINALS_APPEARANCE, 'N/A') as finals_result,
    {{ int_('PTS') }} as pts
from {{ source('landing', 'teamyearbyyearstats__teamstats') }}
where TEAM_ID is not null
{{ latest_file_per('TEAM_ID') }}
