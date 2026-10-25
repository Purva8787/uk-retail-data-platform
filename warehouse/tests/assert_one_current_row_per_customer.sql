-- SCD2 sanity: every customer has exactly one current version and no overlapping windows.
select customer_id
from {{ ref('dim_customer') }}
group by customer_id
having count(*) filter (where is_current) <> 1
union all
select a.customer_id
from {{ ref('dim_customer') }} a
join {{ ref('dim_customer') }} b
  on a.customer_id = b.customer_id and a.customer_key <> b.customer_key
 and a.valid_from < b.valid_to and b.valid_from < a.valid_to
