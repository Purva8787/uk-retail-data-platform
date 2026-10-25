-- Q5: what share of orders ship to surcharge zones (Highlands & Islands, Northern Ireland)?
with orders as (
    select distinct f.order_id, d.month_start, r.delivery_band, r.postcode_area
    from {{ ref('fct_order_items') }} f
    join {{ ref('dim_date') }} d   on d.date_key = f.date_key
    join {{ ref('dim_region') }} r on r.region_key = f.region_key
)

select
    month_start,
    delivery_band,
    count(*)                                                                    as orders,
    round(100.0 * count(*) / sum(count(*)) over (partition by month_start), 2)  as share_of_orders_pct
from orders
group by 1, 2
