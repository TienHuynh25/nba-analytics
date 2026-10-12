-- Task 1.28: an as-of cutoff must not fall inside a season type, because source season totals
-- cannot be cut at a date.
select season, season_type, first_game_date, last_game_date
from {{ ref('int_season_type_status') }}
where straddles_cutoff
