-- Line-level VAT in the fact must add up to the VAT stored on each order (within 1p).
select o.order_id, o.vat_gbp as order_vat, sum(f.vat_gbp) as fact_vat
from {{ ref('stg_orders') }} o
join {{ ref('fct_order_items') }} f on f.order_id = o.order_id
group by o.order_id, o.vat_gbp
having abs(o.vat_gbp - sum(f.vat_gbp)) > 0.01
