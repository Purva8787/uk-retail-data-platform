-- SCD Type 2 customer dimension built from the dbt snapshot.
-- The first version of each customer is back-dated so orders placed before
-- the first snapshot still find a matching row.
with versions as (
    select
        *,
        row_number() over (partition by customer_id order by dbt_valid_from) as version_number
    from {{ ref('customers_snapshot') }}
)

select
    dbt_scd_id                                                    as customer_key,
    customer_id,
    full_name,
    email,
    postcode,
    postcode_area,
    region,
    nation,
    signup_date,
    version_number,
    case when version_number = 1 then '1900-01-01'::timestamptz
         else dbt_valid_from::timestamptz end                     as valid_from,
    coalesce(dbt_valid_to::timestamptz, '9999-12-31'::timestamptz) as valid_to,
    dbt_valid_to is null                                          as is_current
from versions
