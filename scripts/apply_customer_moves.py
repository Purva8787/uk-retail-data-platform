"""
SCD Type 2 demo: 254 customers move house after the first warehouse load.

    python scripts/apply_customer_moves.py     # updates OLTP + re-exports raw.customers
    cd warehouse && dbt snapshot && dbt build  # snapshot closes old rows, opens new ones

Then:  select * from core.dim_customer where customer_id = <id> order by version_number;
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from psycopg2.extras import execute_values

from ingestion.ingest import normalise_postcode, postcode_area
from ingestion.load_pg import connect
from ingestion.rules import is_valid_uk_postcode

movers = json.loads((ROOT / "data" / "raw" / "customers_update.json").read_text())
rows = [(m["customer_id"], normalise_postcode(m["postcode"])) for m in movers]
rows = [(cid, pc) for cid, pc in rows if is_valid_uk_postcode(pc)]

conn = connect()
with conn, conn.cursor() as cur:
    cur.execute("SET search_path TO shop")
    execute_values(cur, "INSERT INTO addresses (postcode, postcode_area) VALUES %s ON CONFLICT (postcode) DO NOTHING",
                   [(pc, postcode_area(pc)) for _, pc in rows])
    execute_values(cur, """UPDATE customers c SET home_address_id = a.address_id
                           FROM (VALUES %s) AS m(customer_id, postcode)
                           JOIN addresses a ON a.postcode = m.postcode
                           WHERE c.customer_id = m.customer_id""", rows)
    cur.execute("SELECT count(*) FROM customers c JOIN addresses a ON a.address_id = c.home_address_id "
                "WHERE a.postcode = ANY(%s)", ([pc for _, pc in rows],))
    print(f"customers now at their new address in OLTP: {cur.fetchone()[0]}")
    cur.execute("""SELECT c.customer_id, c.full_name, c.email, c.signup_date, a.postcode, a.postcode_area, r.region, r.nation
                   FROM customers c JOIN addresses a ON a.address_id = c.home_address_id
                   JOIN regions r ON r.postcode_area = a.postcode_area""")
    df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
conn.close()

conn = connect()
with conn, conn.cursor() as cur:   # TRUNCATE + insert keeps the dbt views that depend on raw.customers intact
    cur.execute("TRUNCATE raw.customers")
    execute_values(cur, f"INSERT INTO raw.customers ({', '.join(df.columns)}) VALUES %s",
                   list(df.itertuples(index=False, name=None)))
conn.close()
print(f"raw.customers re-exported: {len(df)} rows. Now run: cd warehouse && dbt snapshot && dbt build")
