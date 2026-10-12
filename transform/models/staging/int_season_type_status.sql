-- Per (season, season type): first and last game date, and whether the as-of cutoff keeps it.
-- A season type is kept only when all its games are on or before the cutoff. A cutoff that falls
-- inside a season type fails the build (test: as_of_not_inside_season_type), because season totals
-- from the source cannot be cut at a date.
select
    season,
    {{ season_start('season') }} as season_start,
    season_type,
    min(game_date) as first_game_date,
    max(game_date) as last_game_date,
    count(distinct game_id) as games,
    {% if var('as_of') %}
    max(game_date) <= cast('{{ var("as_of") }}' as date) as included,
    min(game_date) <= cast('{{ var("as_of") }}' as date)
        and max(game_date) > cast('{{ var("as_of") }}' as date) as straddles_cutoff
    {% else %}
    true as included,
    false as straddles_cutoff
    {% endif %}
from {{ ref('stg_team_game') }}
group by all
