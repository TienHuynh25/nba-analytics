-- Task 1.20: careers summed over player_season total rows must match NBA.com's own career totals.
-- Skipped in as-of builds, whose careers stop at the cutoff, and in the one-season test fixture.
{% if var('as_of') or var('fixture') %}
select 1 where false
{% else %}
with c as (
    select player_id, season_type,
           sum(gp) as gp, sum(pts) as pts, sum(reb) as reb, sum(ast) as ast,
           sum(fgm) as fgm, sum(ftm) as ftm, sum(fg3m) as fg3m, sum(stl) as stl, sum(blk) as blk
    from {{ ref('player_season') }}
    group by all
)
select c.player_id, c.season_type, c.pts, s.pts as source_pts, c.gp, s.gp as source_gp
from c
join {{ ref('stg_player_career_totals') }} s using (player_id, season_type)
where c.gp is distinct from s.gp
   or c.pts is distinct from s.pts
   or c.reb is distinct from s.reb
   or c.ast is distinct from s.ast
   or c.fgm is distinct from s.fgm
   or c.ftm is distinct from s.ftm
   or c.fg3m is distinct from s.fg3m
   or c.stl is distinct from s.stl
   or c.blk is distinct from s.blk
{% endif %}
