-- Exactly 30 franchises carry a current name, and no current full name repeats.
select count(*) as n, count(distinct full_name) as names
from {{ ref('teams') }}
where is_current
having count(*) <> 30 or count(distinct full_name) <> 30
