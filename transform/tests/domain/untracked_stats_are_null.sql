-- Task 1.15: no stat has a value (not even 0) before its first tracked season.
with {{ availability_cte() }}
{% for tbl in ['player_game', 'player_season'] %}
{% for col, stat in [('stl','stl'), ('blk','blk'), ('fg3m','fg3m'), ('fg3a','fg3a'), ('tov','tov'), ('oreb','oreb')] %}
select '{{ tbl }}' as tbl, '{{ col }}' as col, count(*) as n
from {{ ref(tbl) }} x cross join sa
where x.season_start < sa.{{ stat }} and x.{{ col }} is not null
having count(*) > 0
{{ "union all" if not (loop.last and loop.depth0 == 0) }}
{% endfor %}
{{ "union all" if not loop.last }}
{% endfor %}
