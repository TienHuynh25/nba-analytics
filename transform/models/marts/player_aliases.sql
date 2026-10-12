-- Player x alias (task 1.11): full names, accent-free spellings, and curated nicknames.
with base as (
    select player_id, name as alias, 'full name' as kind from {{ ref('players') }}
    union
    select player_id, strip_accents(name), 'accent-free' from {{ ref('players') }}
    where strip_accents(name) <> name
    union
    select player_id, strip_accents(replace(name, '.', '')), 'no periods' from {{ ref('players') }}
    where name like '%.%'
    union
    -- A bare last name is an alias only when no other player in history shares it
    -- (Wembanyama yes; Curry, Holiday, Ball no: those need a curated alias or a clarification).
    select player_id, last_name, 'last name' from {{ ref('players') }}
    where last_name in (select last_name from {{ ref('players') }} group by 1 having count(*) = 1)
    union
    select player_id, strip_accents(last_name), 'last name' from {{ ref('players') }}
    where last_name in (select last_name from {{ ref('players') }} group by 1 having count(*) = 1)
      and strip_accents(last_name) <> last_name
),
curated as (
    select p.player_id, s.alias, s.kind
    from {{ ref('player_alias_seed') }} s
    join {{ ref('players') }} p on p.name = s.player_name
    -- A curated alias maps to the best-known holder of the name: the one with most seasons.
    qualify row_number() over (partition by s.alias order by (p.to_year - p.from_year) desc) = 1
)
select player_id, alias, lower(strip_accents(alias)) as alias_norm, kind
from (select * from base union all select * from curated)
-- One row per (player, normalized alias); the full name wins over derived spellings.
qualify row_number() over (partition by player_id, lower(strip_accents(alias))
                           order by kind = 'full name' desc, alias) = 1
