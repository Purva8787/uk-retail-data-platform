"""
Module 1 - Python data types & structures.

Reads the raw files into lists of dictionaries, casts every field to the right
Python type and returns clean records plus a summary (rows read, rejected, duplicated).

    IDs        -> int
    money      -> Decimal, GBP, 2 d.p.
    timestamps -> timezone-aware datetime in Europe/London
    duplicates -> caught with a set of seen IDs
    regions    -> postcode area looked up in a dict

Run:  python -m ingestion.ingest
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "reference"
LONDON = ZoneInfo("Europe/London")
PENNY = Decimal("0.01")

# VAT bands held in a dict (rates as Decimal so money maths stays exact)
VAT_RATES: dict[str, Decimal] = {"standard": Decimal("0.20"), "reduced": Decimal("0.05"), "zero": Decimal("0.00")}


@dataclass
class Summary:
    """Counts reported at the end of every ingest."""
    dataset: str
    rows_read: int = 0
    rows_clean: int = 0
    rejected: int = 0
    duplicated: int = 0
    reasons: Counter = field(default_factory=Counter)

    def reject(self, reason: str) -> None:
        self.rejected += 1
        self.reasons[reason] += 1

    def __str__(self) -> str:
        why = ", ".join(f"{k}={v}" for k, v in self.reasons.most_common()) or "-"
        return (f"{self.dataset:<12} read={self.rows_read:>7}  clean={self.rows_clean:>7}  "
                f"rejected={self.rejected:>4}  duplicated={self.duplicated:>4}  [{why}]")


# ---------------------------------------------------------------- type casting
def to_int(value) -> int:
    if value is None or str(value).strip() == "":
        raise ValueError("missing_id")
    return int(str(value).strip())


def to_money(value) -> Decimal:
    """'£49.99', '49.99', 49.99 -> Decimal('49.99'). Raises ValueError on rubbish."""
    if value is None:
        raise ValueError("missing_money")
    text = str(value).strip().replace("£", "").replace(",", "")
    try:
        return Decimal(text).quantize(PENNY, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("bad_money") from exc


def to_london_ts(value: str) -> datetime:
    """Naive strings are UK local time; strings ending in Z (or with an offset) are converted."""
    text = str(value).strip()
    try:
        if text.endswith("Z") or "+" in text[10:]:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.astimezone(LONDON)
        return datetime.fromisoformat(text).replace(tzinfo=LONDON)
    except ValueError as exc:
        raise ValueError("bad_timestamp") from exc


def normalise_postcode(value) -> str | None:
    """'sw1a1aa' -> 'SW1A 1AA'. Returns None if it is too short to be a postcode."""
    if not value:
        return None
    compact = re.sub(r"\s+", "", str(value)).upper()
    if len(compact) < 5:
        return None
    return f"{compact[:-3]} {compact[-3:]}"


def postcode_area(postcode: str | None) -> str | None:
    """The leading letters of the postcode: 'SW1A 1AA' -> 'SW', 'G12 8QQ' -> 'G'."""
    if not postcode:
        return None
    match = re.match(r"^([A-Z]{1,2})\d", postcode)
    return match.group(1) if match else None


def load_area_map(path: Path = REF / "postcode_areas.csv") -> dict[str, dict[str, str]]:
    """{'SW': {'region': 'London', 'nation': 'England'}, ...}"""
    with open(path, newline="") as f:
        return {r["postcode_area"]: {"region": r["region"], "nation": r["nation"]} for r in csv.DictReader(f)}


# ---------------------------------------------------------------- readers
def read_orders(path: Path = RAW / "orders.csv", area_map: dict | None = None) -> tuple[list[dict], Summary]:
    area_map = area_map or load_area_map()
    summary, clean, seen_ids = Summary("orders"), [], set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            summary.rows_read += 1
            try:
                order_id = to_int(row["order_id"])
                if order_id in seen_ids:          # set membership is O(1)
                    summary.duplicated += 1
                    continue
                seen_ids.add(order_id)
                postcode = normalise_postcode(row["postcode"])
                area = postcode_area(postcode)
                geo = area_map.get(area, {})
                clean.append({
                    "order_id": order_id,
                    "customer_id": to_int(row["customer_id"]),
                    "order_ts": to_london_ts(row["order_ts"]),
                    "postcode": postcode,
                    "postcode_area": area,
                    "region": geo.get("region"),
                    "nation": geo.get("nation"),
                    "total_gbp": to_money(row["total_gbp"]),
                    "vat_gbp": to_money(row["vat_gbp"]),
                    "channel": row["channel"].strip().lower(),
                })
            except ValueError as exc:
                summary.reject(str(exc))
    summary.rows_clean = len(clean)
    return clean, summary


def read_order_items(path: Path = RAW / "order_items.csv") -> tuple[list[dict], Summary]:
    summary, clean, seen = Summary("order_items"), [], set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            summary.rows_read += 1
            try:
                key = (to_int(row["order_id"]), row["sku"].strip())
                if key in seen:
                    summary.duplicated += 1
                    continue
                seen.add(key)
                qty = to_int(row["quantity"])
                if qty <= 0:
                    raise ValueError("bad_quantity")
                clean.append({"order_id": key[0], "sku": key[1], "quantity": qty,
                              "unit_price_gbp": to_money(row["unit_price_gbp"])})
            except ValueError as exc:
                summary.reject(str(exc))
    summary.rows_clean = len(clean)
    return clean, summary


def read_customers(path: Path = RAW / "customers.json", area_map: dict | None = None) -> tuple[list[dict], Summary]:
    area_map = area_map or load_area_map()
    summary, clean, seen = Summary("customers"), [], set()
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    for rec in records:
        summary.rows_read += 1
        try:
            cid = to_int(rec.get("customer_id"))
            if cid in seen:
                summary.duplicated += 1
                continue
            seen.add(cid)
            postcode = normalise_postcode(rec.get("postcode"))
            if postcode is None:
                raise ValueError("missing_postcode")
            area = postcode_area(postcode)
            clean.append({
                "customer_id": cid,
                "name": rec["name"].strip(),
                "email": rec["email"].strip().lower(),
                "postcode": postcode,
                "postcode_area": area,
                "region": area_map.get(area, {}).get("region"),
                "signup_date": date.fromisoformat(rec["signup_date"]),
            })
        except (ValueError, KeyError) as exc:
            summary.reject(str(exc))
    summary.rows_clean = len(clean)
    return clean, summary


def read_products(path: Path = RAW / "products.csv") -> tuple[list[dict], Summary]:
    summary, clean, seen = Summary("products"), [], set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            summary.rows_read += 1
            sku = row["sku"].strip()
            if sku in seen:
                summary.duplicated += 1
                continue
            seen.add(sku)
            band = row["vat_band"].strip().lower()
            if band not in VAT_RATES:
                summary.reject("bad_vat_band")
                continue
            try:
                clean.append({"sku": sku, "name": row["name"].strip(), "category": row["category"].strip(),
                              "vat_band": band, "unit_price_gbp": to_money(row["unit_price_gbp"])})
            except ValueError as exc:
                summary.reject(str(exc))
    summary.rows_clean = len(clean)
    return clean, summary


def ingest_all() -> tuple[dict[str, list[dict]], list[Summary]]:
    """Read every raw file. Returns ({dataset: records}, [summaries])."""
    area_map = load_area_map()
    orders, s1 = read_orders(area_map=area_map)
    items, s2 = read_order_items()
    customers, s3 = read_customers(area_map=area_map)
    products, s4 = read_products()
    return ({"orders": orders, "order_items": items, "customers": customers, "products": products},
            [s1, s2, s3, s4])


if __name__ == "__main__":
    data, summaries = ingest_all()
    print("Ingest summary")
    for s in summaries:
        print(" ", s)
    sample = data["orders"][0]
    print("\nExample clean order:", {k: (str(v) if isinstance(v, (Decimal, datetime)) else v) for k, v in sample.items()})
