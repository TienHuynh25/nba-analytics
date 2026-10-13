select stat, first_season, first_season_start, note from {{ ref('stat_availability') }}
-- Deterministic row order (DEF-021): a total order, so every build stores the same rows in
-- the same order.
order by all
