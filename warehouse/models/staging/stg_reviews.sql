select
    review_id,
    sku,
    customer_id::int                       as customer_id,
    order_id::int                          as order_id,
    rating::int                            as rating,
    verified_purchase::boolean             as verified_purchase,
    string_to_array(nullif(tags, ''), ',') as tags,
    review_ts::timestamptz                 as review_ts
from {{ source('raw', 'reviews') }}
