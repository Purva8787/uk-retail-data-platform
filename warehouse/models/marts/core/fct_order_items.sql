-- Grain: one row per product per order.
-- region_key comes from the DELIVERY postcode on the order (where it shipped);
-- customer_key is the customer version that was valid when the order was placed.
select
    li.order_item_id,
    li.order_id,
    d.date_key,
    c.customer_key,
    p.product_key,
    r.region_key,
    o.order_ts,
    o.channel,
    li.quantity,
    li.unit_price_gbp,
    li.line_total_gbp                         as total_gbp,
    li.line_vat_gbp                           as vat_gbp,
    li.line_total_gbp - li.line_vat_gbp       as net_gbp,
    o.is_high_value_order,
    o.delivery_band
from {{ ref('int_order_items_priced') }} li
join {{ ref('int_orders') }} o       on o.order_id = li.order_id
join {{ ref('dim_date') }} d         on d.date_day = o.order_date_uk
join {{ ref('dim_product') }} p      on p.sku = li.sku
join {{ ref('dim_region') }} r       on r.postcode_area = o.postcode_area
left join {{ ref('dim_customer') }} c
    on c.customer_id = o.customer_id
   and o.order_ts >= c.valid_from
   and o.order_ts <  c.valid_to
