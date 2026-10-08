-- One row per player (task 1.11).
select
    p.player_id,
    p.name,
    p.first_name,
    p.last_name,
    p.birth_date,
    p.position,
    p.from_year,
    p.to_year,
    p.active,
    p.draft_year,
    r.rookie_season
from {{ ref('stg_players') }} p
left join (
    -- The rookie season is the player's first season in player_season (spec gold rule Q05).
    select player_id, min(season) as rookie_season
    from {{ ref('player_season') }}
    where season_type = 'Regular Season'
    group by 1
) r using (player_id)
where p.played or r.rookie_season is not null
