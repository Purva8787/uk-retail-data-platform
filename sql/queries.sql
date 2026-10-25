-- =====================================================================
-- Albion Basket - 15 business questions (Module 3: SQL fundamentals)
-- Run:  psql -d albion -f sql/queries.sql
-- All money is GBP, VAT-inclusive unless the column says net.
-- =====================================================================
SET search_path TO shop;

-- Q1. Top 10 products by revenue.
-- Line revenue = quantity x price paid. ORDER BY + LIMIT gives the top 10.
SELECT p.sku,
       p.name,
       p.category,
       SUM(oi.quantity * oi.unit_price_gbp) AS revenue_gbp,
       SUM(oi.quantity)                     AS units_sold
FROM order_items oi
JOIN products p ON p.sku = oi.sku
GROUP BY p.sku, p.name, p.category
ORDER BY revenue_gbp DESC
LIMIT 10;

-- Q2. Revenue by UK nation, keeping only nations above £50,000 (GROUP BY + HAVING).
SELECT r.nation,
       COUNT(*)           AS orders,
       SUM(o.total_gbp)   AS revenue_gbp
FROM orders o
JOIN addresses a ON a.address_id = o.delivery_address_id
JOIN regions r   ON r.postcode_area = a.postcode_area
GROUP BY r.nation
HAVING SUM(o.total_gbp) > 50000
ORDER BY revenue_gbp DESC;

-- Q3. Revenue and average order value by region.
SELECT r.nation,
       r.region,
       COUNT(*)                           AS orders,
       SUM(o.total_gbp)                   AS revenue_gbp,
       ROUND(AVG(o.total_gbp), 2)         AS avg_order_value_gbp
FROM orders o
JOIN addresses a ON a.address_id = o.delivery_address_id
JOIN regions r   ON r.postcode_area = a.postcode_area
GROUP BY r.nation, r.region
ORDER BY revenue_gbp DESC;

-- Q4. Which regions are growing fastest? Compare Jan-Jun 2025 with Jan-Jun 2024.
-- FILTER keeps both periods in one pass; NULLIF avoids divide-by-zero.
SELECT r.region,
       SUM(o.total_gbp) FILTER (WHERE o.order_ts >= '2024-01-01' AND o.order_ts < '2024-07-01') AS h1_2024_gbp,
       SUM(o.total_gbp) FILTER (WHERE o.order_ts >= '2025-01-01' AND o.order_ts < '2025-07-01') AS h1_2025_gbp,
       ROUND(100.0 * (SUM(o.total_gbp) FILTER (WHERE o.order_ts >= '2025-01-01' AND o.order_ts < '2025-07-01')
             / NULLIF(SUM(o.total_gbp) FILTER (WHERE o.order_ts >= '2024-01-01' AND o.order_ts < '2024-07-01'), 0) - 1), 1)
                                                                                        AS growth_pct
FROM orders o
JOIN addresses a ON a.address_id = o.delivery_address_id
JOIN regions r   ON r.postcode_area = a.postcode_area
GROUP BY r.region
ORDER BY growth_pct DESC;

-- Q5. Monthly revenue trend (date functions). Timestamps are converted to UK time first,
-- so an order at 00:30 BST on 1 June counts in June, not May.
SELECT DATE_TRUNC('month', o.order_ts AT TIME ZONE 'Europe/London')::date AS month,
       COUNT(*)          AS orders,
       SUM(o.total_gbp)  AS revenue_gbp
FROM orders o
GROUP BY 1
ORDER BY 1;

-- Q6. Delivery bands with CASE WHEN: how many orders go to each band?
SELECT CASE
           WHEN a.postcode_area IN ('IV', 'HS', 'KW', 'ZE') THEN 'Highlands & Islands'
           WHEN a.postcode_area = 'BT'                      THEN 'Northern Ireland'
           ELSE 'Mainland'
       END                                                   AS delivery_band,
       COUNT(*)                                              AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)    AS pct_of_orders
FROM orders o
JOIN addresses a ON a.address_id = o.delivery_address_id
GROUP BY 1
ORDER BY orders DESC;

-- Q7. Delivery fees collected by band (surcharge zones pay on every order).
SELECT r.delivery_band,
       COUNT(*)                     AS orders,
       SUM(o.delivery_fee_gbp)      AS delivery_fees_gbp,
       ROUND(AVG(o.delivery_fee_gbp), 2) AS avg_fee_gbp
FROM orders o
JOIN addresses a ON a.address_id = o.delivery_address_id
JOIN regions r   ON r.postcode_area = a.postcode_area
GROUP BY r.delivery_band
ORDER BY orders DESC;

-- Q8. VAT collected per calendar quarter.
SELECT TO_CHAR(o.order_ts AT TIME ZONE 'Europe/London', 'YYYY-"Q"Q') AS vat_quarter,
       SUM(o.total_gbp)                AS gross_gbp,
       SUM(o.vat_gbp)                  AS vat_gbp,
       SUM(o.total_gbp - o.vat_gbp)    AS net_gbp
FROM orders o
GROUP BY 1
ORDER BY 1;

-- Q9. VAT per UK tax year (6 April to 5 April). An order on 5 April 2024 is tax year 2023/24.
SELECT CASE
           WHEN (o.order_ts AT TIME ZONE 'Europe/London')::date
                >= MAKE_DATE(EXTRACT(YEAR FROM o.order_ts AT TIME ZONE 'Europe/London')::int, 4, 6)
           THEN EXTRACT(YEAR FROM o.order_ts AT TIME ZONE 'Europe/London')::int
           ELSE EXTRACT(YEAR FROM o.order_ts AT TIME ZONE 'Europe/London')::int - 1
       END                                AS tax_year_start,
       SUM(o.vat_gbp)                     AS vat_gbp,
       COUNT(*)                           AS orders
FROM orders o
GROUP BY 1
ORDER BY 1;

-- Q10. VAT by band: check the stored order VAT against VAT recomputed from the lines.
-- VAT inside a VAT-inclusive price = gross x rate / (1 + rate).
SELECT v.vat_band,
       v.rate,
       SUM(oi.quantity * oi.unit_price_gbp)                                  AS gross_gbp,
       ROUND(SUM(oi.quantity * oi.unit_price_gbp * v.rate / (1 + v.rate)), 2) AS vat_gbp
FROM order_items oi
JOIN products p  ON p.sku = oi.sku
JOIN vat_rates v ON v.vat_band = p.vat_band
GROUP BY v.vat_band, v.rate
ORDER BY vat_gbp DESC;

-- Q11. High-value orders (£500+) by channel.
SELECT o.channel,
       COUNT(*) FILTER (WHERE o.total_gbp >= 500)                         AS high_value_orders,
       COUNT(*)                                                           AS all_orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE o.total_gbp >= 500) / COUNT(*), 2) AS pct_high_value
FROM orders o
GROUP BY o.channel
ORDER BY high_value_orders DESC;

-- Q12. Share of orders that qualify for free delivery (£40+) by nation.
SELECT r.nation,
       ROUND(100.0 * AVG(CASE WHEN o.total_gbp >= 40 THEN 1 ELSE 0 END), 1) AS pct_orders_40_plus
FROM orders o
JOIN addresses a ON a.address_id = o.delivery_address_id
JOIN regions r   ON r.postcode_area = a.postcode_area
GROUP BY r.nation
ORDER BY pct_orders_40_plus DESC;

-- Q13. Top 10 customers by lifetime spend, with their home region.
SELECT c.customer_id,
       c.full_name,
       r.region,
       COUNT(o.order_id)  AS orders,
       SUM(o.total_gbp)   AS lifetime_spend_gbp,
       MIN(o.order_ts)::date AS first_order,
       MAX(o.order_ts)::date AS last_order
FROM customers c
JOIN addresses a ON a.address_id = c.home_address_id
JOIN regions r   ON r.postcode_area = a.postcode_area
JOIN orders o    ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.full_name, r.region
ORDER BY lifetime_spend_gbp DESC
LIMIT 10;

-- Q14. Repeat-purchase rate: what share of customers ordered more than once?
-- LEFT JOIN keeps customers who never ordered.
SELECT COUNT(*)                                             AS customers,
       COUNT(*) FILTER (WHERE n_orders = 0)                 AS never_ordered,
       COUNT(*) FILTER (WHERE n_orders = 1)                 AS one_order,
       COUNT(*) FILTER (WHERE n_orders >= 2)                AS repeat_customers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE n_orders >= 2)
             / NULLIF(COUNT(*) FILTER (WHERE n_orders >= 1), 0), 1) AS repeat_rate_pct
FROM (
    SELECT c.customer_id, COUNT(o.order_id) AS n_orders
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id
) t;

-- Q15. Busiest days: top 10 dates by orders. Black Friday and December should dominate.
SELECT (o.order_ts AT TIME ZONE 'Europe/London')::date        AS order_date,
       TO_CHAR((o.order_ts AT TIME ZONE 'Europe/London')::date, 'Dy') AS weekday,
       COUNT(*)                                               AS orders,
       SUM(o.total_gbp)                                       AS revenue_gbp
FROM orders o
GROUP BY 1, 2
ORDER BY orders DESC
LIMIT 10;
