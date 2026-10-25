select
    customer_id::int        as customer_id,
    full_name,
    lower(trim(email))      as email,
    upper(postcode)         as postcode,
    upper(postcode_area)    as postcode_area,
    region,
    nation,
    signup_date::date       as signup_date
from {{ source('raw', 'customers') }}
