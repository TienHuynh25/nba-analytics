-- One row per franchise (task 1.12). NBA.com lineage: team_id is the franchise across
-- relocations, so Seattle and Oklahoma City share one franchise_id.
select
    team_id as franchise_id,
    city || ' ' || name as current_name,
    start_year,
    end_year,
    defunct
from {{ ref('stg_franchise_history') }}
where is_franchise_row
