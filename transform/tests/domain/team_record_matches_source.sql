-- Regular-season W-L computed from games must equal NBA.com's TeamYearByYearStats W-L.
-- Catches pairing and season-type errors in games.
select ts.team_id, ts.season, ts.wins, ts.losses, ty.wins as source_wins, ty.losses as source_losses
from {{ ref('team_season') }} ts
join {{ ref('stg_team_year') }} ty on ty.team_id = ts.team_id and ty.season = ts.season
left join {{ ref('known_team_record_gaps') }} k on k.team_id = ts.team_id and k.season = ts.season
where ts.season_type = 'Regular Season'
  and (ts.wins <> ty.wins or ts.losses <> ty.losses)
  -- Allowed only where a known source gap explains the exact difference in games.
  and not (k.team_id is not null and ty.gp - ts.gp = k.games_missing)
