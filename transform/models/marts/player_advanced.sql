-- NBA.com published advanced stats per player x season x season type (1996-97 on).
select a.*, {{ season_start('a.season') }} as season_start
from {{ ref('stg_player_advanced') }} a
join {{ ref('int_season_type_status') }} x using (season, season_type)
where x.included
