select
    order_id::int                         as order_id,
    customer_id::int                      as customer_id,
    order_ts::timestamptz                 as order_ts,
    (order_ts at time zone 'Europe/London')::date as order_date_uk,
    lower(channel)                        as channel,
    upper(postcode)                       as postcode,
    upper(postcode_area)                  as postcode_area,
    total_gbp::numeric(12, 2)             as total_gbp,
    vat_gbp::numeric(12, 2)               as vat_gbp,
    delivery_fee_gbp::numeric(6, 2)       as delivery_fee_gbp
from {{ source('raw', 'orders') }}
