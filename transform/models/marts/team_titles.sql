-- Franchise x season champion and Finals opponent (task 1.17, gap G2). Titles count by franchise.
-- A title counts in an as-of build only when that season's playoffs end on or before the cutoff.
with fin as (
    select ty.*
    from {{ ref('stg_team_year') }} ty
    join {{ ref('int_season_type_status') }} x
      on x.season = ty.season and x.season_type = 'Playoffs' and x.included
    where ty.finals_result in ('LEAGUE CHAMPION', 'FINALS APPEARANCE')
)
select
    c.team_id as franchise_id,
    c.team_id,
    c.season,
    c.season_start,
    c.city || ' ' || c.name as champion_name,
    o.team_id as opponent_team_id,
    o.city || ' ' || o.name as opponent_name
from fin c
left join fin o on o.season = c.season and o.finals_result = 'FINALS APPEARANCE'
where c.finals_result = 'LEAGUE CHAMPION'
