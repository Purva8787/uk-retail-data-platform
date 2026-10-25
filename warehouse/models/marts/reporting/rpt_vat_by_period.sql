-- Q4: VAT collected per calendar quarter and per UK tax year (6 April to 5 April), split by VAT band.
select
    d.tax_year,
    d.year_quarter,
    p.vat_band,
    count(distinct f.order_id) as orders,
    sum(f.total_gbp)           as gross_gbp,
    sum(f.vat_gbp)             as vat_gbp,
    sum(f.net_gbp)             as net_gbp
from {{ ref('fct_order_items') }} f
join {{ ref('dim_date') }} d    on d.date_key = f.date_key
join {{ ref('dim_product') }} p on p.product_key = f.product_key
group by 1, 2, 3
