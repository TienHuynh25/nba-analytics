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
stint_teams as (
    select distinct player_id, season, season_type, team_id
    from {{ ref('stg_player_season_rows') }}
    where not is_total_row
),
team_games as (
    select g.player_id, g.season, g.season_type, g.team_id, g.game_date, g.game_id,
           s.team_id is not null as is_stint_team,
           min(g.game_date) over (partition by g.player_id, g.season, g.season_type, g.team_id)
               as team_first_date
    from {{ ref('stg_player_game') }} g
    left join stint_teams s using (player_id, season, season_type, team_id)
),
last_team as (
    -- The team of the player's latest game in that season type. Tie-break rule (DEF-021), used
    -- only when the latest date has games for two teams (5 player-seasons, 1980-81..1984-85):
    -- 1. a team the source lists as one of the player's stints for that season (player 76444
    --    in 1982-83 has one stint, LAL, but a same-day game logged for LAC);
    -- 2. the stint the player joined later (later first game that season; this matches the
    --    source's own chronological stint order in playercareerstats);
    -- 3. the higher game_id. game_id is unique per player and season type: a total order.
    select player_id, season, season_type, team_id
    from team_games
    qualify row_number() over (partition by player_id, season, season_type
                               order by game_date desc, is_stint_team desc,
                                        team_first_date desc, game_id desc) = 1
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
-- Deterministic row order (DEF-021): a total order, so every build stores the same rows in
-- the same order.
order by all
