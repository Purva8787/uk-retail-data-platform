-- Q3: which products get the worst reviews, and does that hurt repeat purchases?
-- repeat_after_purchase_rate = share of buyers who placed ANY later order after first buying this product.
with first_buy as (
    select c.customer_id, f.product_key, min(f.order_ts) as first_bought_ts
    from {{ ref('fct_order_items') }} f
    join {{ ref('dim_customer') }} c on c.customer_key = f.customer_key
    group by 1, 2
),

last_order as (
    select c.customer_id, max(f.order_ts) as last_order_ts
    from {{ ref('fct_order_items') }} f
    join {{ ref('dim_customer') }} c on c.customer_key = f.customer_key
    group by 1
),

product_repeat as (
    select
        fb.product_key,
        count(*)                                                    as buyers,
        avg(case when lo.last_order_ts > fb.first_bought_ts then 1.0 else 0 end) as repeat_after_purchase_rate
    from first_buy fb
    join last_order lo using (customer_id)
    group by 1
)

select
    p.sku,
    p.product_name,
    p.category,
    p.review_count,
    p.avg_rating,
    p.is_poorly_rated,
    pr.buyers,
    round(pr.repeat_after_purchase_rate * 100, 1) as repeat_after_purchase_pct
from {{ ref('dim_product') }} p
left join product_repeat pr using (product_key)
