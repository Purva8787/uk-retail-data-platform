-- 5 April belongs to the old tax year, 6 April starts the new one.
select date_day, tax_year
from {{ ref('dim_date') }}
where (date_day = '2024-04-05' and tax_year <> '2023/24')
   or (date_day = '2024-04-06' and tax_year <> '2024/25')
