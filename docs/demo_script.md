# 10-minute demo for Albion Basket leadership

**Rule from the brief:** show the question, the pipeline that answers it, and the one number that should change a decision.

Before you start: `docker compose up -d`, run `bash scripts/run_all.sh` once, open these tabs: the README lineage
image, `notebooks/analysis.ipynb` (scrolled to Q1), a terminal in `warehouse/`, and a SQL client connected to `albion`.

---

## 0:00–1:00 The problem
> "Orders live in PostgreSQL, reviews and web events in MongoDB, and finance rebuilds reports by hand every month.
> Nobody trusts the numbers because nobody can reproduce them. I built one pipeline that does."

## 1:00–3:00 The pipeline (show `docs/lineage.png`)
Walk left to right in one sentence each:
- **Ingest (Python):** 48,241 raw orders in; 150 duplicates and 75 bad rows caught and logged, never silently dropped.
- **Store:** 3NF PostgreSQL with constraints (a negative total *cannot* be saved); MongoDB for reviews and clickstream.
- **Transform (pandas):** joins both stores; VAT reconciles to the penny on every order.
- **Warehouse (dbt):** star schema, one row per product per order.

## 3:00–5:00 Proof it's trustworthy (live)
```bash
cd warehouse && dbt build
```
> "96 checks pass: every fact row points at a real customer, product, date and region; VAT in the warehouse equals
> VAT on every order; revenue isn't lost or doubled in any join."

Then the SCD2 history demo:
```bash
python ../scripts/apply_customer_moves.py && dbt snapshot && dbt build
```
```sql
select customer_id, version_number, postcode, region, valid_from, valid_to, is_current
from core.dim_customer where customer_id = 6 order by version_number;
```
> "Customer 6 moved from the North West to the West Midlands. Old orders stay credited to where she lived then."

## 5:00–8:00 The five answers (one chart each, ~35 seconds per chart)
1. **Regions:** Scotland +51% year on year; South West −7%. *Marketing spend is pointed at the wrong end of the country.*
2. **Calendar:** Black Friday +134%, Cyber Monday +94%, bank holidays +22%, Christmas Day −74%. *Plan drivers and slots around this.*
3. **Reviews:** five products average about 2 stars (hold the punchline for the one-number slot).
4. **VAT:** £143.0k in 2023/24 → £159.2k in 2024/25, by 6 April tax year, straight from `rpt_vat_by_period`. *Finance can stop building this by hand.*
5. **Surcharge zones:** 6.8% of orders, rising from 5.5% to 7.8% as Scotland and NI grow. *Courier contracts priced on the old mix will under-budget.*

## 8:00–9:00 The one number
> "Customers whose **first** order contains one of these five products place **4.7 orders instead of 8.6**:
> 46% less. They're cheap snacks and a draught excluder, but they're costing us loyal customers.
> **Recommendation: fix or delist these five SKUs this quarter**, then watch first-order repeat rate in `rpt_product_reviews_repeat`."

Be honest if asked: it's observational, not a controlled experiment, but the gap is large and the fix is cheap.

## 9:00–10:00 What's next
- Schedule the pipeline (Airflow or dbt Cloud) instead of running it by hand.
- Move the warehouse to Snowflake or BigQuery (only `dim_date` and the profile change).
- A/B test the delisting to prove cause and effect.
- Fix mobile checkout: 63% of mobile baskets are abandoned vs 39% on desktop.

---

### Likely questions
- **Why both SQL and Mongo?** Money needs constraints and transactions; reviews and events change shape and are read whole. See `mongo/design_note.md`.
- **Why is `unit_price_gbp` on order_items?** It's the price at the time of sale, not today's price.
- **Why back-date the first SCD2 version?** Otherwise orders placed before the first snapshot would have no customer row to join to.
- **How do you know VAT is right?** Line-level VAT, rounded half-up like a till, is tested against every order total in dbt.
