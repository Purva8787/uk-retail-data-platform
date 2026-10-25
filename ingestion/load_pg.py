"""
Module 4 - load clean, rule-checked records into the PostgreSQL OLTP schema.

    python -m ingestion.load_pg

Credentials come from .env (copy .env.example). Nothing secret is ever committed.
The whole load runs in one transaction: it either all lands or none of it does.
"""
from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from ingestion.ingest import REF, VAT_RATES, ingest_all, postcode_area
from ingestion.rules import apply_rules, delivery_band, is_valid_uk_postcode

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("load_pg")


def connect():
    load_dotenv(ROOT / ".env")
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"), port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DB", "albion"), user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD"),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("rules").setLevel(logging.ERROR)

    data, summaries = ingest_all()
    for s in summaries:
        log.info("ingest  %s", s)
    orders, rejected = apply_rules(data["orders"])
    log.info("rules   valid=%d rejected=%d", len(orders), len(rejected))

    with open(REF / "postcode_areas.csv", newline="") as f:
        regions = [(r["postcode_area"], r["region"], r["nation"], delivery_band(r["postcode_area"]))
                   for r in csv.DictReader(f)]
    known_areas = {r[0] for r in regions}

    customers = [c for c in data["customers"]
                 if is_valid_uk_postcode(c["postcode"]) and c["postcode_area"] in known_areas]
    customer_ids = {c["customer_id"] for c in customers}
    orphan_orders = [o for o in orders if o["customer_id"] not in customer_ids]
    orders = [o for o in orders if o["customer_id"] in customer_ids]
    order_ids = {o["order_id"] for o in orders}
    skus = {p["sku"] for p in data["products"]}
    items = [i for i in data["order_items"] if i["order_id"] in order_ids and i["sku"] in skus]
    log.info("orphans dropped: orders=%d items=%d", len(orphan_orders), len(data["order_items"]) - len(items))

    postcodes = sorted({c["postcode"] for c in customers} | {o["postcode"] for o in orders})

    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute((ROOT / "sql" / "schema.sql").read_text())
            cur.execute("SET search_path TO shop")
            execute_values(cur, "INSERT INTO regions VALUES %s", regions)
            execute_values(cur, "INSERT INTO vat_rates VALUES %s", list(VAT_RATES.items()))
            address_rows = [(pc, postcode_area(pc)) for pc in postcodes]
            ids = execute_values(cur, "INSERT INTO addresses (postcode, postcode_area) VALUES %s RETURNING address_id, postcode",
                                 address_rows, page_size=5000, fetch=True)
            address_id = {pc: aid for aid, pc in ids}
            execute_values(cur, "INSERT INTO customers VALUES %s",
                           [(c["customer_id"], c["name"], c["email"], address_id[c["postcode"]], c["signup_date"])
                            for c in customers], page_size=5000)
            execute_values(cur, "INSERT INTO products VALUES %s",
                           [(p["sku"], p["name"], p["category"], p["vat_band"], p["unit_price_gbp"])
                            for p in data["products"]])
            execute_values(cur, "INSERT INTO orders VALUES %s",
                           [(o["order_id"], o["customer_id"], address_id[o["postcode"]], o["order_ts"], o["channel"],
                             o["total_gbp"], o["vat_gbp"], o["delivery_fee_gbp"]) for o in orders], page_size=5000)
            execute_values(cur, "INSERT INTO order_items VALUES %s",
                           [(i["order_id"], i["sku"], i["quantity"], i["unit_price_gbp"]) for i in items],
                           page_size=10000)
            for table in ("regions", "vat_rates", "addresses", "customers", "products", "orders", "order_items"):
                cur.execute(f"SELECT count(*) FROM {table}")
                log.info("loaded  shop.%-12s %8d rows", table, cur.fetchone()[0])
    except psycopg2.Error as exc:
        log.error("load failed, transaction rolled back: %s", exc)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
