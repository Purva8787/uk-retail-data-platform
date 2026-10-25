-- Q1: which regions and nations drive revenue, and which are growing fastest?
with monthly as (
    select
        d.month_start,
        r.nation,
        r.region,
        count(distinct f.order_id) as orders,
        sum(f.total_gbp)           as revenue_gbp
    from {{ ref('fct_order_items') }} f
    join {{ ref('dim_date') }} d   on d.date_key = f.date_key
    join {{ ref('dim_region') }} r on r.region_key = f.region_key
    group by 1, 2, 3
)

select
    *,
    lag(revenue_gbp, 12) over (partition by region order by month_start)               as revenue_same_month_last_year_gbp,
    round(100.0 * (revenue_gbp / nullif(lag(revenue_gbp, 12) over (partition by region order by month_start), 0) - 1), 1)
                                                                                         as yoy_growth_pct,
    round(100.0 * revenue_gbp / sum(revenue_gbp) over (partition by month_start), 2)    as share_of_month_pct
from monthly
