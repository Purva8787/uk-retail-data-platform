-- Orders enriched with region, delivery band and business flags.
select
    o.*,
    pa.region,
    pa.nation,
    pa.delivery_band,
    o.total_gbp >= 500  as is_high_value_order,
    o.total_gbp >= 40   as qualifies_free_delivery
from {{ ref('stg_orders') }} o
join {{ ref('stg_postcode_areas') }} pa on pa.postcode_area = o.postcode_area
