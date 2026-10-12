{# Text -> typed helpers for landing columns (all VARCHAR). #}
{% macro int_(col) -%} try_cast(try_cast({{ col }} as double) as integer) {%- endmacro %}
{% macro num_(col) -%} try_cast({{ col }} as double) {%- endmacro %}
{% macro param_(name) -%} json_extract_string(_params, '$.{{ name }}') {%- endmacro %}

{# '2024-25' -> 2024 #}
{% macro season_start(col) -%} cast(substr({{ col }}, 1, 4) as integer) {%- endmacro %}

{# stats.nba.com SEASON_ID '22024' -> '2024-25' #}
{% macro season_from_id(col) -%}
  (substr({{ col }}, 2, 4) || '-' || lpad(cast((cast(substr({{ col }}, 2, 4) as integer) + 1) % 100 as varchar), 2, '0'))
{%- endmacro %}

{# Game ID prefix -> season type. 006 is the NBA Cup final, kept out of regular-season stats. #}
{% macro season_type_from_game_id(col) -%}
  case substr({{ col }}, 1, 3)
    when '002' then 'Regular Season'
    when '004' then 'Playoffs'
    when '005' then 'PlayIn'
    when '006' then 'Cup Final'
  end
{%- endmacro %}

{# Keep only rows from the latest fetch per natural key. #}
{% macro latest_per(keys) -%}
  qualify row_number() over (partition by {{ keys }} order by _fetched_at desc, _file desc) = 1
{%- endmacro %}

{# Keep only rows from the latest file per request (per-entity endpoints: the whole response wins). #}
{% macro latest_file_per(keys) -%}
  qualify _fetched_at = max(_fetched_at) over (partition by {{ keys }})
{%- endmacro %}

{# As-of cutoff (task 1.28). #}
{% macro as_of_date_filter(col) -%}
  {%- if var('as_of') -%} {{ col }} <= cast('{{ var("as_of") }}' as date) {%- else -%} true {%- endif -%}
{%- endmacro %}

{# stat_availability as one row with a column per stat (first season start year). #}
{% macro availability_cte() -%}
  sa as (
    pivot (select stat, first_season_start from {{ ref('stat_availability') }})
    on stat using any_value(first_season_start)
  )
{%- endmacro %}

{# NULL, not 0, for a stat not tracked in the row's season (spec: Untracked stats are NULL). #}
{% macro tracked(col, stat, season_col='season_start') -%}
  case when {{ season_col }} >= sa.{{ stat }} then {{ col }} end
{%- endmacro %}

{% macro tracked_counting(prefix='') -%}
  {%- for col, stat in [('minutes','minutes'), ('fgm','fgm'), ('fga','fga'), ('fg3m','fg3m'),
       ('fg3a','fg3a'), ('ftm','ftm'), ('fta','fta'), ('oreb','oreb'), ('dreb','dreb'),
       ('reb','reb'), ('ast','ast'), ('stl','stl'), ('blk','blk'), ('tov','tov'), ('pf','pf'),
       ('pts','pts')] %}
    {{ tracked(prefix ~ col, stat) }} as {{ col }}{{ "," if not loop.last }}
  {%- endfor %}
{%- endmacro %}
