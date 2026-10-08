-- Player x game box score (task 1.15). NULL, not 0, for stats not tracked that season.
-- Before 1996-97 some box scores are partial (ingest/ENDPOINTS.md, G1): seasons and careers read
-- player_season, never a sum over this table.
with {{ availability_cte() }},
g as (
    select p.* replace (coalesce(gm.season_type, p.season_type) as season_type),
           {{ season_start('p.season') }} as season_start
    from {{ ref('stg_player_game') }} p
    left join {{ ref('games') }} gm using (game_id)
    where {{ as_of_date_filter('p.game_date') }}
)
select
    g.game_id,
    g.player_id,
    g.team_id,
    g.season,
    g.season_start,
    g.season_type,
    g.game_date,
    g.matchup,
    g.wl,
    {{ tracked_counting('g.') }},
    {{ tracked("g.plus_minus", "plus_minus") }} as plus_minus
from g cross join sa
