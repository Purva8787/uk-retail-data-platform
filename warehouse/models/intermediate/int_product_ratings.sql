select
    sku,
    count(*)                                   as review_count,
    round(avg(rating), 2)                      as avg_rating,
    count(*) filter (where rating <= 2)        as low_rating_count
from {{ ref('stg_reviews') }}
group by sku
