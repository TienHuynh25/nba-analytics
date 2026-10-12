-- One row per (franchise, name era). NBA.com lineage: TEAM_ID is stable across relocations.
with src as (
    select *, false as defunct from {{ source('landing', 'franchisehistory__franchisehistory') }}
    union all by name
    select *, true as defunct from {{ source('landing', 'franchisehistory__defunctteams') }}
),
latest as (select * from src {{ latest_file_per('_key') }})
select
    {{ int_('TEAM_ID') }} as team_id,
    TEAM_CITY as city,
    TEAM_NAME as name,
    {{ int_('START_YEAR') }} as start_year,
    {{ int_('END_YEAR') }} as end_year,
    {{ int_('LEAGUE_TITLES') }} as league_titles,
    defunct,
    -- The first row per team_id spans the franchise's whole life; the rest are name eras.
    row_number() over (partition by TEAM_ID order by {{ int_('YEARS') }} desc,
                       {{ int_('START_YEAR') }}) = 1 as is_franchise_row
from latest
