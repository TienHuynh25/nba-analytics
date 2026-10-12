-- Decision 0008: from 1996-97, a hand-entered single-game record must match an NBA.com box
-- score: the named player has a game on or before valid_from with exactly that value.
{% set cols = {'pts': 'pts', 'fg3m': 'fg3m', 'reb': 'reb', 'ast': 'ast', 'stl': 'stl', 'blk': 'blk'} %}
select r.record, r.player, r.value
from {{ ref('records_curated') }} r
join {{ ref('players') }} p on p.name = r.player
where r.record_kind = 'single_game'
  and cast(r.valid_from as date) >= date '1996-10-01'
  and not exists (
      select 1 from {{ ref('player_game') }} g
      where g.player_id = p.player_id
        and g.game_date <= cast(r.valid_from as date)
        and case r.stat
            {% for k, c in cols.items() %} when '{{ k }}' then g.{{ c }} {% endfor %}
            end = try_cast(r.value as double)
  )
