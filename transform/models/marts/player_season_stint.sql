-- Player x season x season type x team (task 1.16): one row per team a player played for.
-- Never SUM these rows for league totals or leaders; read player_season.
with {{ availability_cte() }},
r as (
    select s.*
    from {{ ref('stg_player_season_rows') }} s
    join {{ ref('int_season_type_status') }} st using (season, season_type)
    where not s.is_total_row and st.included
)
select
    r.player_id,
    r.season,
    r.season_start,
    r.season_type,
    r.team_id,
    r.team_abbreviation,
    r.player_age,
    r.gp,
    {{ tracked('r.gs', 'gs') }} as gs,
    {{ tracked_counting('r.') }}
from r cross join sa
