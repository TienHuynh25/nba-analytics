-- Player x season x award (task 1.17). In an as-of build an award counts only once it is known:
-- in-season awards (All-Star, weekly and monthly) when that regular season is complete, all
-- others (MVP, ROY, All-NBA, ...) when that season's playoffs are complete.
with a as (
    select a.*, coalesce(t.known_at, 'postseason_end') as known_at
    from {{ ref('stg_awards') }} a
    left join {{ ref('award_timing') }} t on t.award = a.award
),
status as (
    select season,
           bool_or(included) filter (where season_type = 'Regular Season') as rs_done,
           bool_or(included) filter (where season_type = 'Playoffs') as po_done
    from {{ ref('int_season_type_status') }}
    group by 1
)
select
    a.player_id,
    a.season,
    a.season_start,
    a.award,
    a.award_type,
    a.team_name,
    a.team_number,
    a.conference,
    a.month,
    a.week
from a
join status s using (season)
where case a.known_at when 'regular_season_end' then s.rs_done else s.po_done end
