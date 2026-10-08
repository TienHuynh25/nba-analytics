-- Team x alias: current names, cities, abbreviations and curated nicknames.
with cur as (
    select t.team_id, t.full_name, t.city, t.name
    from {{ ref('teams') }} t where t.is_current
),
abbr as (
    select team_id, any_value(team_abbreviation) as abbreviation
    from {{ ref('stg_team_game') }}
    where season = (select max(season) from {{ ref('stg_team_game') }})
    group by 1
)
select team_id, alias, lower(alias) as alias_norm, kind from (
    select team_id, full_name as alias, 'full name' as kind from cur
    union all select team_id, name, 'name' from cur
    union all select team_id, city, 'city' from cur
    union all select team_id, abbreviation, 'abbreviation' from abbr
    union all
    select a.team_id, s.alias, 'nickname'
    from {{ ref('team_alias_seed') }} s join abbr a on a.abbreviation = s.team_abbreviation
)
-- One row per (team, normalized alias); official names win over curated nicknames.
qualify row_number() over (
    partition by team_id, lower(alias)
    order by case kind when 'full name' then 0 when 'name' then 1 when 'city' then 2
                       when 'abbreviation' then 3 else 4 end
) = 1
