"""Refresh the bank-holiday seed from GOV.UK.

    python scripts/fetch_bank_holidays.py
Writes data/reference/uk_bank_holidays.csv and warehouse/seeds/uk_bank_holidays.csv.
"""
import csv
import shutil
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.gov.uk/bank-holidays.json"

data = requests.get(URL, timeout=10).json()
out = ROOT / "data" / "reference" / "uk_bank_holidays.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["division", "holiday_date", "title"])
    for division, block in data.items():
        for e in block["events"]:
            w.writerow([division, e["date"], e["title"]])
shutil.copy(out, ROOT / "warehouse" / "seeds" / "uk_bank_holidays.csv")
print(f"wrote {out} and the dbt seed")
