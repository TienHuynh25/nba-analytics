-- Player x title season (spec: a player's titles are the seasons he appeared in at least one
-- playoff game for the champion).
select distinct
    s.player_id,
    t.season,
    t.season_start,
    t.franchise_id
from {{ ref('player_season_stint') }} s
join {{ ref('team_titles') }} t on t.team_id = s.team_id and t.season = s.season
where s.season_type = 'Playoffs' and s.gp >= 1
