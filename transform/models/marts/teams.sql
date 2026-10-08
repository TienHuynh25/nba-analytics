-- One row per franchise name era (task 1.12), from consecutive seasons with the same city and
-- name in TeamYearByYearStats. Eras never overlap, unlike FranchiseHistory's name rows.
with seasons as (
    select team_id, city, name, season, season_start,
           season_start - row_number() over (partition by team_id, city, name
                                             order by season_start) as grp
    from {{ ref('stg_team_year') }}
),
eras as (
    select team_id, city, name,
           min(season_start) as first_season_start,
           max(season_start) as last_season_start
    from seasons
    group by team_id, city, name, grp
)
select
    team_id,
    team_id as franchise_id,
    city,
    name,
    city || ' ' || name as full_name,
    first_season_start,
    last_season_start,
    -- Seasons start in October; validity runs from Aug 1 of the first season to Jul 31 after the last.
    make_date(first_season_start, 8, 1) as valid_from,
    make_date(last_season_start + 1, 7, 31) as valid_to,
    -- Current = the name an active franchise uses in the latest season (defunct franchises,
    -- e.g. the 1949-50 Denver Nuggets, are never current).
    last_season_start = (select max(season_start) from {{ ref('stg_team_year') }}) as is_current
from eras
