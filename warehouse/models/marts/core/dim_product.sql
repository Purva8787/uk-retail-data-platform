-- SCD Type 1: current product attributes plus review stats from MongoDB.
select
    md5(p.sku)                                  as product_key,
    p.sku,
    p.product_name,
    p.category,
    p.vat_band,
    v.vat_rate,
    p.unit_price_gbp                            as current_unit_price_gbp,
    coalesce(r.review_count, 0)                 as review_count,
    r.avg_rating,
    coalesce(r.review_count >= 20 and r.avg_rating < 2.5, false) as is_poorly_rated
from {{ ref('stg_products') }} p
join {{ ref('vat_rates') }} v on v.vat_band = p.vat_band
left join {{ ref('int_product_ratings') }} r on r.sku = p.sku
