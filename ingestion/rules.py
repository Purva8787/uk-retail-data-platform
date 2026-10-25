"""
Module 2 - comparison operators & loops.

Applies Albion Basket's UK business rules to every order:
  * valid UK postcode format (e.g. SW1A 1AA)          -> otherwise skip + log
  * total_gbp must be >= 0                            -> otherwise skip + log
  * delivery band: mainland / highlands_islands (IV, HS, KW, ZE) / northern_ireland (BT)
  * flag orders of £500 or more as high value
  * free delivery from £40 (mainland); surcharge zones always pay a surcharge
  * postcodes.io lookups retried with a while loop, up to 3 attempts

Run:  python -m ingestion.rules
"""
from __future__ import annotations

import logging
import re
import time
from decimal import Decimal

import requests

log = logging.getLogger("rules")

UK_POSTCODE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][ABD-HJLNP-UW-Z]{2}$")
HIGHLANDS_ISLANDS = ("IV", "HS", "KW", "ZE")
NORTHERN_IRELAND = ("BT",)

HIGH_VALUE_GBP = Decimal("500.00")
FREE_DELIVERY_GBP = Decimal("40.00")
STANDARD_DELIVERY_GBP = Decimal("3.99")
SURCHARGE_GBP = {"highlands_islands": Decimal("5.95"), "northern_ireland": Decimal("4.95"), "mainland": Decimal("0.00")}

POSTCODES_IO = "https://api.postcodes.io/postcodes/{}"
MAX_ATTEMPTS = 3


def is_valid_uk_postcode(postcode: str | None) -> bool:
    return bool(postcode) and UK_POSTCODE.match(postcode) is not None


def delivery_band(area: str | None) -> str:
    if area in HIGHLANDS_ISLANDS:
        return "highlands_islands"
    elif area in NORTHERN_IRELAND:
        return "northern_ireland"
    else:
        return "mainland"


def delivery_fee(total: Decimal, band: str) -> Decimal:
    base = Decimal("0.00") if total >= FREE_DELIVERY_GBP else STANDARD_DELIVERY_GBP
    return base + SURCHARGE_GBP[band]


def apply_rules(orders: list[dict]) -> tuple[list[dict], list[dict]]:
    """Loop over every order. Returns (valid_orders, rejected_orders_with_reason)."""
    valid, rejected = [], []
    for o in orders:
        if not is_valid_uk_postcode(o.get("postcode")):
            log.warning("order %s skipped: bad postcode %r", o.get("order_id"), o.get("postcode"))
            rejected.append({**o, "reason": "bad_postcode"})
            continue
        if o["total_gbp"] < 0:
            log.warning("order %s skipped: negative total %s", o["order_id"], o["total_gbp"])
            rejected.append({**o, "reason": "negative_total"})
            continue
        if o.get("region") is None:
            log.warning("order %s skipped: unknown postcode area %s", o["order_id"], o.get("postcode_area"))
            rejected.append({**o, "reason": "unknown_area"})
            continue

        band = delivery_band(o["postcode_area"])
        o["delivery_band"] = band
        o["is_high_value"] = o["total_gbp"] >= HIGH_VALUE_GBP
        o["free_delivery"] = o["total_gbp"] >= FREE_DELIVERY_GBP and band == "mainland"
        o["delivery_fee_gbp"] = delivery_fee(o["total_gbp"], band)
        valid.append(o)
    return valid, rejected


def lookup_postcode(postcode: str, session: requests.Session | None = None,
                    max_attempts: int = MAX_ATTEMPTS, backoff: float = 0.5) -> dict | None:
    """Ask postcodes.io for region/country/local authority. Retries up to 3 times.

    Returns a dict, or None if the postcode does not exist or every attempt failed.
    """
    http = session or requests
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        try:
            resp = http.get(POSTCODES_IO.format(postcode.replace(" ", "")), timeout=5)
            if resp.status_code == 404:
                return None                      # a real answer: postcode not found, don't retry
            resp.raise_for_status()
            result = resp.json()["result"]
            return {"postcode": result["postcode"], "region": result.get("region"),
                    "country": result["country"], "local_authority": result.get("admin_district")}
        except (requests.RequestException, KeyError, ValueError) as exc:
            log.warning("postcodes.io attempt %d/%d failed for %s: %s", attempt, max_attempts, postcode, exc)
            if attempt < max_attempts:
                time.sleep(backoff * attempt)
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    from ingestion.ingest import read_orders

    orders, _ = read_orders()
    valid, rejected = apply_rules(orders)
    from collections import Counter
    print(f"valid={len(valid)}  rejected={len(rejected)}  reasons={dict(Counter(r['reason'] for r in rejected))}")
    print("delivery bands:", dict(Counter(o["delivery_band"] for o in valid)))
    print("high value orders:", sum(o["is_high_value"] for o in valid))
    print("free delivery:", sum(o["free_delivery"] for o in valid))
    print("postcodes.io check for SW1A 1AA:", lookup_postcode("SW1A 1AA"))
