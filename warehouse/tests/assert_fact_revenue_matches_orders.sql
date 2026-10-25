-- Gross revenue in the fact must equal total_gbp on every order: nothing lost or doubled in the joins.
select o.order_id, o.total_gbp, sum(f.total_gbp) as fact_total
from {{ ref('stg_orders') }} o
left join {{ ref('fct_order_items') }} f on f.order_id = o.order_id
group by o.order_id, o.total_gbp
having coalesce(sum(f.total_gbp), -1) <> o.total_gbp
