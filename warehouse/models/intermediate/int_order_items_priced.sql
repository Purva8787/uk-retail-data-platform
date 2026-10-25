-- One row per order line with gross, VAT and net. Prices are VAT-inclusive,
-- so VAT = gross x rate / (1 + rate), rounded half-up per line like the till.
select
    oi.order_item_id,
    oi.order_id,
    oi.sku,
    oi.quantity,
    oi.unit_price_gbp,
    p.vat_band,
    v.vat_rate,
    (oi.quantity * oi.unit_price_gbp)::numeric(12, 2)                                        as line_total_gbp,
    round(oi.quantity * oi.unit_price_gbp * v.vat_rate / (1 + v.vat_rate), 2)::numeric(12, 2) as line_vat_gbp
from {{ ref('stg_order_items') }} oi
join {{ ref('stg_products') }} p on p.sku = oi.sku
join {{ ref('vat_rates') }} v on v.vat_band = p.vat_band
