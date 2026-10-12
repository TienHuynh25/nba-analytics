-- One row per shot attempt (task 1.18), as Parquet partitioned by season inside the snapshot's own
-- folder (NBA_SHOTS_DIR = data/snapshots/<snapshot_id>/shots), so swap, rollback and the manifest
-- checksum cover it.
{{ config(
    materialized='external',
    location=env_var('NBA_SHOTS_DIR', '../data/build/dev_shots'),
    options={'partition_by': 'season', 'overwrite_or_ignore': true}
) }}
select s.*
from {{ ref('stg_shots') }} s
join {{ ref('int_season_type_status') }} x using (season, season_type)
where x.included and {{ as_of_date_filter('s.game_date') }}
