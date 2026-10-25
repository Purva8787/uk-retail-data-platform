select
    order_id::int || '-' || sku          as order_item_id,
    order_id::int                        as order_id,
    sku,
    quantity::int                        as quantity,
    unit_price_gbp::numeric(10, 2)       as unit_price_gbp
from {{ source('raw', 'order_items') }}
