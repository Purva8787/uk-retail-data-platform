-- Known Black Fridays: 24 Nov 2023, 29 Nov 2024, 28 Nov 2025. Exactly one per year.
select calendar_year, count(*) filter (where is_black_friday) as n
from {{ ref('dim_date') }}
group by calendar_year
having count(*) filter (where is_black_friday) <> 1
union all
select extract(year from date_day)::int, 0
from {{ ref('dim_date') }}
where date_day in ('2023-11-24', '2024-11-29', '2025-11-28') and not is_black_friday
