-- Every player NBA.com lists, joined to per-player info where fetched.
with roster as (
    select *
    from {{ source('landing', 'commonallplayers__commonallplayers') }}
    {{ latest_per('PERSON_ID') }}
),
info as (
    select *
    from {{ source('landing', 'commonplayerinfo__commonplayerinfo') }}
    {{ latest_per('PERSON_ID') }}
)
select
    {{ int_('r.PERSON_ID') }} as player_id,
    r.DISPLAY_FIRST_LAST as name,
    coalesce(i.FIRST_NAME, split_part(r.DISPLAY_FIRST_LAST, ' ', 1)) as first_name,
    coalesce(i.LAST_NAME, nullif(split_part(r.DISPLAY_LAST_COMMA_FIRST, ',', 1), '')) as last_name,
    try_cast(substr(i.BIRTHDATE, 1, 10) as date) as birth_date,
    nullif(i.POSITION, '') as position,
    {{ int_('r.FROM_YEAR') }} as from_year,
    {{ int_('r.TO_YEAR') }} as to_year,
    {{ int_('r.ROSTERSTATUS') }} = 1 as active,
    r.GAMES_PLAYED_FLAG = 'Y' as played,
    nullif(i.DRAFT_YEAR, 'Undrafted') as draft_year
from roster r
left join info i on i.PERSON_ID = r.PERSON_ID
