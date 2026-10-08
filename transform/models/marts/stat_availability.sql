select stat, first_season, first_season_start, note from {{ ref('stat_availability') }}
