select
    {{ int_('PERSON_ID') }} as player_id,
    DESCRIPTION as award,
    SEASON as season,
    {{ season_start('SEASON') }} as season_start,
    TEAM as team_name,
    nullif(ALL_NBA_TEAM_NUMBER, '') as team_number,
    nullif(CONFERENCE, '') as conference,
    nullif(MONTH, '') as month,
    nullif(WEEK, '') as week,
    TYPE as award_type,
    SUBTYPE1 as subtype1, SUBTYPE2 as subtype2
from {{ source('landing', 'playerawards__playerawards') }}
where PERSON_ID is not null
{{ latest_file_per('PERSON_ID') }}
