select
    sku,
    name                              as product_name,
    category,
    lower(vat_band)                   as vat_band,
    unit_price_gbp::numeric(10, 2)    as unit_price_gbp
from {{ source('raw', 'products') }}
