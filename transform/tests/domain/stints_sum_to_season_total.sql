-- Task 1.20: for traded players, counting stats over stints must sum to the source total row.
-- Minutes are allowed max(1 minute per stint, 1%) slack: NBA.com rounds stint minutes and total
-- minutes separately. Every other stat must match exactly, except source errors listed (with a
-- note each) in the known_stint_total_gaps seed.
{% set stats = ['gp', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta', 'reb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts'] %}
with s as (
    select player_id, season, season_type,
        sum(minutes) as minutes,
        {% for c in stats %} sum({{ c }}) as {{ c }}{{ "," if not loop.last }} {% endfor %}
    from {{ ref('player_season_stint') }}
    group by all
)
select t.player_id, t.season, t.season_type
from {{ ref('player_season') }} t
join s using (player_id, season, season_type)
left join {{ ref('known_stint_total_gaps') }} k
  on k.player_id = t.player_id and k.season = t.season and k.season_type = t.season_type
where t.team_count > 1 and k.player_id is null and (
    abs(t.minutes - s.minutes) > greatest(t.team_count, 0.01 * t.minutes) or
    {% for c in stats %}
    round(t.{{ c }}) is distinct from round(s.{{ c }}){{ " or" if not loop.last }}
    {% endfor %}
)
