-- Curated and computed records (task 1.17, gap G1). Single-game maxima come from player_game,
-- whose game logs are complete for every season (ingest/ENDPOINTS.md); the top 10 per stat are
-- kept. Career counts that early box scores cannot support (e.g. career triple-doubles) come from
-- the curated seed, pending the owner's G1 decision on Basketball-Reference.
with single_game as (
    {% for stat, label in [('pts', 'Most points in a game'), ('fg3m', 'Most 3-pointers made in a game'),
                           ('reb', 'Most rebounds in a game'), ('ast', 'Most assists in a game')] %}
    select '{{ label }}' as record, 'single_game' as record_kind, '{{ stat }}' as stat,
           player_id, game_id, game_date, season, season_type, {{ stat }} as value,
           game_date as valid_from, 'nba_api leaguegamelog' as source
    from {{ ref('player_game') }}
    where season_type = 'Regular Season' and {{ stat }} is not null
    qualify rank() over (order by {{ stat }} desc) <= 10
    {{ "union all" if not loop.last }}
    {% endfor %}
),
curated as (
    select award as record, award_category as record_kind, null as stat,
           p.player_id, null as game_id, null::date as game_date, null as season,
           null as season_type, try_cast(value as double) as value,
           cast(valid_from as date) as valid_from, source
    from {{ ref('records_curated') }} r
    left join {{ ref('players') }} p on p.name = r.holder_name
    where {{ as_of_date_filter('cast(r.valid_from as date)') }}
)
select * from single_game
union all by name
select * from curated
