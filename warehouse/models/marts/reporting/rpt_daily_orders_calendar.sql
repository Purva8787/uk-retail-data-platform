-- Q2: how do bank holidays, Black Friday and Christmas change daily orders?
with daily as (
    select
        d.date_day,
        d.day_name,
        d.is_weekend,
        d.is_bank_holiday_england_wales,
        d.is_bank_holiday_scotland,
        d.is_bank_holiday_northern_ireland,
        d.holiday_name,
        d.is_black_friday,
        d.is_cyber_monday,
        d.is_christmas_run_up,
        count(distinct f.order_id) as orders,
        coalesce(sum(f.total_gbp), 0) as revenue_gbp
    from {{ ref('dim_date') }} d
    left join {{ ref('fct_order_items') }} f on f.date_key = d.date_key
    where d.date_day between (select min(order_date_uk) from {{ ref('int_orders') }})
                         and (select max(order_date_uk) from {{ ref('int_orders') }})
    group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
)

select
    *,
    case
        when is_black_friday then 'Black Friday'
        when is_cyber_monday then 'Cyber Monday'
        when extract(month from date_day) = 12 and extract(day from date_day) = 25 then 'Christmas Day'
        when is_christmas_run_up then 'Christmas run-up (1-24 Dec)'
        when is_bank_holiday_england_wales then 'Bank holiday (E&W)'
        when is_weekend then 'Weekend'
        else 'Normal weekday'
    end as day_type,
    round(avg(orders) over (order by date_day rows between 14 preceding and 14 following), 1) as orders_28d_avg,
    round(100.0 * (orders / nullif(avg(orders) over (order by date_day rows between 14 preceding and 14 following), 0) - 1), 1)
        as vs_28d_avg_pct
from daily
