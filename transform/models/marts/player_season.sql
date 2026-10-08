-- Player x season x season type (task 1.16): the season total across all teams, taken from the
-- source's total row (TEAM_ID 0, 'TOT') for traded players, else the single team row. Never a
-- SUM of stints. Leaders, totals and careers read only this table.
with {{ availability_cte() }},
rows_ as (
    select s.*,
           count(*) filter (where not s.is_total_row)
               over (partition by s.player_id, s.season, s.season_type) as team_count
    from {{ ref('stg_player_season_rows') }} s
    join {{ ref('int_season_type_status') }} st using (season, season_type)
    where st.included
),
totals as (
    select * from rows_
    where is_total_row or team_count = 1
    -- A traded player has both team rows and a TOT row: keep the TOT row.
    qualify row_number() over (partition by player_id, season, season_type
                               order by is_total_row desc) = 1
),
last_team as (
    -- The team of the player's latest game in that season type.
    select player_id, season, season_type, team_id
    from {{ ref('stg_player_game') }}
    qualify row_number() over (partition by player_id, season, season_type
                               order by game_date desc) = 1
)
select
    t.player_id,
    t.season,
    t.season_start,
    t.season_type,
    t.team_count,
    lt.team_id as last_team_id,
    t.player_age,
    t.gp,
    {{ tracked('t.gs', 'gs') }} as gs,
    {{ tracked_counting('t.') }}
from totals t
cross join sa
left join last_team lt using (player_id, season, season_type)
