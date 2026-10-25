"""
Generate synthetic but realistically British raw data for Albion Basket.

Outputs (data/raw/):
    orders.csv, order_items.csv, customers.json, products.csv,
    reviews.json, events.json, customers_update.json (used later for the SCD2 demo)

The data deliberately contains problems the pipeline must handle:
duplicate order IDs, bad postcodes, "£" in money fields, negative totals,
missing customer IDs, mixed timestamp formats, duplicate customers, messy emails.

Run:  python data/generate_data.py          (fixed seed, so results are reproducible)
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

SEED = 42
START, END = date(2023, 1, 1), date(2025, 6, 30)
N_CUSTOMERS, N_PRODUCTS = 6000, 200
LONDON = ZoneInfo("Europe/London")

ROOT = Path(__file__).resolve().parent
RAW, REF = ROOT / "raw", ROOT / "reference"
rng = np.random.default_rng(SEED)
random.seed(SEED)

VAT = {"standard": Decimal("0.20"), "reduced": Decimal("0.05"), "zero": Decimal("0")}

# --- regions: population-ish weights and annual growth (Scotland/Wales grow fastest) ---
REGION_WEIGHT = {
    "London": 13, "South East": 14, "South West": 8.5, "East of England": 9.5,
    "East Midlands": 7, "West Midlands": 9, "North West": 11, "North East": 4,
    "Yorkshire and The Humber": 8.2, "Wales": 4.7, "Scotland": 8.2, "Northern Ireland": 2.8,
}
REGION_GROWTH = {
    "London": 1.00, "South East": 1.06, "South West": 1.08, "East of England": 1.07,
    "East Midlands": 1.10, "West Midlands": 1.09, "North West": 1.12, "North East": 1.20,
    "Yorkshire and The Humber": 1.11, "Wales": 1.30, "Scotland": 1.35, "Northern Ireland": 1.25,
}
# Highland & Island areas get a bigger slice of Scotland than their size suggests
AREA_BOOST = {"IV": 3.0, "HS": 1.5, "KW": 1.5, "ZE": 1.2, "G": 3.0, "EH": 3.0, "AB": 2.0}

FIRST = ("Oliver George Harry Jack Noah Charlie Jacob Alfie Freddie Oscar Arthur Leo Muhammad "
         "Thomas James William Rhys Callum Ewan Ciaran Olivia Amelia Isla Ava Mia Ivy Lily Isabella "
         "Rosie Sophia Grace Freya Florence Evie Poppy Eilidh Siobhan Ffion Niamh Aoife Priya Aisha").split()
LAST = ("Smith Jones Williams Taylor Brown Davies Evans Wilson Thomas Johnson Roberts Robinson "
        "Thompson Wright Walker White Edwards Hughes Green Hall Lewis Harris Clarke Patel Jackson "
        "Wood Turner Martin Cooper Hill Ward Morris Moore Clark Lee King Baker MacDonald Campbell "
        "Stewart Murray O'Neill Kelly Murphy Khan Ali Begum Morgan Price Griffiths").split()

CATEGORIES = [  # (category, vat_band, price range, nouns)
    ("Fresh Produce", "zero", (0.6, 4.5), "Apples,Bananas,Carrots,Leeks,Potatoes,Strawberries,Spinach,Tomatoes,Onions,Pears"),
    ("Bakery", "zero", (0.9, 3.5), "Sourdough,Crumpets,Bloomer,Bagels,Teacakes,Wholemeal Loaf,Scones,Hot Cross Buns"),
    ("Dairy & Eggs", "zero", (0.8, 6.0), "Semi-Skimmed Milk,Mature Cheddar,Salted Butter,Greek Yoghurt,Free Range Eggs,Double Cream,Wensleydale"),
    ("Pantry", "zero", (0.7, 8.0), "Porridge Oats,Baked Beans,Fusilli Pasta,Basmati Rice,Tea Bags,Ground Coffee,Marmalade,Plain Flour"),
    ("Snacks & Confectionery", "standard", (0.8, 6.0), "Ready Salted Crisps,Milk Chocolate,Digestive Biscuits,Flapjack,Clotted Cream Fudge,Sea Salt Popcorn"),
    ("Soft Drinks", "standard", (0.9, 5.0), "Cloudy Lemonade,Cola,Orange Squash,Sparkling Water,Ginger Beer"),
    ("Household", "standard", (1.5, 12.0), "Washing Up Liquid,Bin Bags,Kitchen Roll,Laundry Pods,Thick Bleach"),
    ("Homeware", "standard", (6.0, 120.0), "Duvet,Towel Set,Kettle,Toaster,Table Lamp,Cushion,Mug Set,Saucepan Set"),
    ("Baby & Child", "reduced", (25.0, 180.0), "Child Car Seat,Booster Seat,Infant Car Seat"),
    ("Energy Saving", "reduced", (8.0, 90.0), "Draught Excluder,Loft Insulation Roll,Smart Thermostat,Pipe Lagging"),
]
ADJ = "Classic Organic British Scottish Welsh Value Finest Everyday Farmhouse Heritage Seaside".split()


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def make_postcode(area: str) -> str:
    district = rng.integers(1, 20 if len(area) == 1 else 40)
    inward_letters = "ABDEFGHJLNPQRSTUWXYZ"
    return f"{area}{district} {rng.integers(0, 10)}{random.choice(inward_letters)}{random.choice(inward_letters)}"


def load_areas() -> dict[str, list[str]]:
    by_region: dict[str, list[str]] = {}
    with open(REF / "postcode_areas.csv") as f:
        for row in csv.DictReader(f):
            by_region.setdefault(row["region"], []).append(row["postcode_area"])
    return by_region


def make_products() -> list[dict]:
    products, sku_n = [], 10001
    per_cat = N_PRODUCTS // len(CATEGORIES)
    for cat, band, (lo, hi), nouns in CATEGORIES:
        nouns = nouns.split(",")
        for i in range(per_cat):
            products.append({
                "sku": f"AB-{sku_n}",
                "name": f"Albion {random.choice(ADJ)} {nouns[i % len(nouns)]}",
                "category": cat,
                "vat_band": band,
                "unit_price_gbp": money(round(float(rng.uniform(lo, hi)), 1) - 0.01 if hi > 5 else rng.uniform(lo, hi)),
            })
            sku_n += 1
    # ~8% of products are poor quality -> bad reviews, and they hurt repeat purchase
    bad = set(rng.choice([p["sku"] for p in products], size=12, replace=False))
    for p in products:
        p["_quality"] = 1.9 if p["sku"] in bad else float(rng.uniform(3.7, 4.6))
    return products


def make_customers(by_region) -> list[dict]:
    regions = list(REGION_WEIGHT)
    w = np.array([REGION_WEIGHT[r] for r in regions]); w = w / w.sum()
    customers = []
    for cid in range(1, N_CUSTOMERS + 1):
        region = regions[rng.choice(len(regions), p=w)]
        areas = by_region[region]
        aw = np.array([AREA_BOOST.get(a, 1.0) for a in areas]); aw = aw / aw.sum()
        area = areas[rng.choice(len(areas), p=aw)]
        first, last = random.choice(FIRST), random.choice(LAST)
        customers.append({
            "customer_id": cid,
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower().replace(chr(39), '')}{cid}@example.co.uk",
            "postcode": make_postcode(area),
            "_region": region,
            "_propensity": float(min(rng.pareto(3.0) + 0.5, 4.0)),   # a few loyal customers, capped
        })
    return customers


def daily_multiplier(d: date, holidays: set[date]) -> float:
    m = 1.0
    m *= {0: 1.05, 1: 0.95, 2: 0.95, 3: 1.0, 4: 1.0, 5: 0.9, 6: 1.2}[d.weekday()]  # Sunday shop
    if d.month == 12 and d.day <= 21:
        m *= 1.55
    if d.month == 12 and d.day in (24, 25, 26):
        m *= {24: 0.7, 25: 0.25, 26: 0.8}[d.day]
    if d.month == 1 and d.day <= 10:
        m *= 0.8
    # Black Friday = day after the 4th Thursday of November; Cyber Monday 3 days later
    nov1 = date(d.year, 11, 1)
    black_friday = nov1 + timedelta(days=(3 - nov1.weekday()) % 7 + 21 + 1)
    if d == black_friday:
        m *= 3.2
    elif d == black_friday + timedelta(days=3):
        m *= 2.1
    elif black_friday - timedelta(days=3) <= d <= black_friday + timedelta(days=2):
        m *= 1.4
    if d in holidays and not (d.month == 12):
        m *= 1.25  # long-weekend stock-ups
    return m


def to_raw_ts(local_dt: datetime) -> str:
    """Most rows are naive UK local time; ~5% arrive as UTC ISO strings ending in Z."""
    if rng.random() < 0.05:
        return local_dt.replace(tzinfo=LONDON).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    by_region = load_areas()
    products = make_products()
    customers = make_customers(by_region)
    with open(REF / "uk_bank_holidays.csv") as f:
        ew_holidays = {date.fromisoformat(r["holiday_date"]) for r in csv.DictReader(f)
                       if r["division"] == "england-and-wales"}

    regions = list(REGION_WEIGHT)
    cust_by_region = {r: [c for c in customers if c["_region"] == r] for r in regions}
    cust_w = {r: np.array([c["_propensity"] for c in cs]) / sum(c["_propensity"] for c in cs)
              for r, cs in cust_by_region.items()}
    pop = 1 / np.arange(1, len(products) + 1) ** 0.8
    rng.shuffle(pop)
    cat_w = {"Homeware": 0.04, "Baby & Child": 0.015, "Energy Saving": 0.04, "Household": 0.5}
    pop = pop * np.array([cat_w.get(p["category"], 1.0) * (0.25 if p["_quality"] < 2.5 else 1.0) for p in products])
    pop = pop / pop.sum()
    homeware = [p for p in products if p["category"] == "Homeware"]

    # ---------- orders ----------
    raw_orders = []
    d = START
    while d <= END:
        years = (d - START).days / 365.25
        lam = 48 * (1.12 ** years) * daily_multiplier(d, ew_holidays)
        rw = np.array([REGION_WEIGHT[r] * REGION_GROWTH[r] ** years for r in regions]); rw = rw / rw.sum()
        for _ in range(rng.poisson(lam)):
            region = regions[rng.choice(len(regions), p=rw)]
            cust = cust_by_region[region][rng.choice(len(cust_by_region[region]), p=cust_w[region])]
            hour = int(rng.choice(24, p=np.array([1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 5, 5, 6, 6, 5, 5, 5, 6, 8, 9, 9, 8, 5, 3]) / 105))
            ts = datetime(d.year, d.month, d.day, hour, int(rng.integers(0, 60)), int(rng.integers(0, 60)))
            if rng.random() < 0.006:     # rare bulk homeware order (drives £500+ flags)
                items = [(p, int(rng.integers(8, 20))) for p in random.sample(homeware, 2)]
            else:
                k = min(4 + rng.poisson(6), 18)
                idx = rng.choice(len(products), size=k, replace=False, p=pop)
                items = [(products[i], int(rng.choice([1, 1, 1, 2, 2, 3]))) for i in idx]
            raw_orders.append({"cust": cust, "ts": ts, "items": items})
        d += timedelta(days=1)

    # Customers whose first order contained a poor product come back less often
    raw_orders.sort(key=lambda o: o["ts"])
    first_bad: dict[int, bool] = {}
    kept = []
    for o in raw_orders:
        cid = o["cust"]["customer_id"]
        if cid not in first_bad:
            first_bad[cid] = any(p["_quality"] < 2.5 for p, _ in o["items"])
            kept.append(o)
        elif first_bad[cid] and rng.random() < 0.55:
            continue
        else:
            kept.append(o)

    orders, order_items = [], []
    for n, o in enumerate(kept):
        oid = 100001 + n
        total, vat = Decimal("0"), Decimal("0")
        for p, q in o["items"]:
            line = p["unit_price_gbp"] * q
            line_vat = money(line * VAT[p["vat_band"]] / (1 + VAT[p["vat_band"]]))
            total += line; vat += line_vat
            order_items.append({"order_id": oid, "sku": p["sku"], "quantity": q, "unit_price_gbp": p["unit_price_gbp"]})
        o["order_id"] = oid
        orders.append({
            "order_id": oid, "customer_id": o["cust"]["customer_id"], "order_ts": to_raw_ts(o["ts"]),
            "postcode": o["cust"]["postcode"], "total_gbp": money(total), "vat_gbp": money(vat),
            "channel": random.choices(["web", "ios_app", "android_app"], weights=[45, 33, 22])[0],
        })

    # ---------- inject dirty data ----------
    for o in random.sample(orders, 25):
        o["total_gbp"] = f"£{o['total_gbp']}"                      # parseable
    for o in random.sample(orders, 20):
        o["postcode"] = o["postcode"].lower().replace(" ", "")     # normalisable
    bad_pc = random.sample(orders, 40)
    for o, v in zip(bad_pc, ["INVALID", "12345", "", "SW1A", "ZZ99 9ZZZ"] * 8):
        o["postcode"] = v                                          # reject
    for o in random.sample(orders, 15):
        o["total_gbp"] = f"-{o['total_gbp']}".replace("£", "")      # reject
    for o in random.sample(orders, 10):
        o["customer_id"] = ""                                      # reject
    for o in random.sample(orders, 10):
        o["order_ts"] = "31/02/2024 25:61"                          # reject
    orders += [dict(o) for o in random.sample(orders, 150)]         # duplicates
    random.shuffle(orders)

    with open(RAW / "orders.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["order_id", "customer_id", "order_ts", "postcode", "total_gbp", "vat_gbp", "channel"])
        w.writeheader(); w.writerows(orders)
    with open(RAW / "order_items.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["order_id", "sku", "quantity", "unit_price_gbp"])
        w.writeheader(); w.writerows(order_items)
    with open(RAW / "products.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "name", "category", "vat_band", "unit_price_gbp"])
        w.writeheader(); w.writerows([{k: v for k, v in p.items() if not k.startswith("_")} for p in products])

    # ---------- customers ----------
    first_order = {}
    for o in kept:
        first_order.setdefault(o["cust"]["customer_id"], o["ts"].date())
    cust_out = []
    for c in customers:
        fo = first_order.get(c["customer_id"], END)
        signup = fo - timedelta(days=int(rng.integers(0, 120)))
        cust_out.append({"customer_id": c["customer_id"], "name": c["name"], "email": c["email"],
                         "postcode": c["postcode"], "signup_date": signup.isoformat()})
    for c in random.sample(cust_out, 30):
        c["email"] = f"  {c['email'].upper()} "
    cust_out += [dict(c) for c in random.sample(cust_out, 20)]
    with open(RAW / "customers.json", "w") as f:
        json.dump(cust_out, f, indent=1)

    # customers who moved after the first extract (feeds the SCD2 snapshot demo)
    movers = []
    seen = set()
    for c in random.sample(cust_out, 260):
        if c["customer_id"] in seen:
            continue
        seen.add(c["customer_id"])
        region = random.choice(list(by_region))
        movers.append({**c, "email": c["email"].strip().lower(),
                       "postcode": make_postcode(random.choice(by_region[region]))})
    with open(RAW / "customers_update.json", "w") as f:
        json.dump(movers, f, indent=1)

    # ---------- reviews ----------
    texts = {
        1: ["Arrived damaged and tasted off.", "Very poor, would not buy again.", "Broke within a week."],
        2: ["Not great value for money.", "Disappointing quality.", "Smaller than expected."],
        3: ["Does the job.", "Average, nothing special.", "Fine but a bit pricey."],
        4: ["Good quality, would buy again.", "Nice and fresh.", "Solid product."],
        5: ["Brilliant, absolutely love it!", "Excellent quality and quick delivery.", "Lovely, cracking value."],
    }
    tags_pool = {1: ["damaged", "poor_quality", "late_delivery", "refund"], 2: ["poor_quality", "small", "pricey"],
                 3: ["ok", "pricey"], 4: ["fresh", "good_value"], 5: ["fresh", "good_value", "gift", "fast_delivery"]}
    by_sku = {p["sku"]: p for p in products}
    reviews, rid = [], 1
    for o in kept:
        for p, _ in o["items"]:
            if rng.random() < 0.03:
                r = int(np.clip(round(rng.normal(p["_quality"], 0.9)), 1, 5))
                ts = (o["ts"] + timedelta(days=int(rng.integers(2, 21)))).replace(tzinfo=LONDON)
                reviews.append({
                    "review_id": f"R{rid:07d}", "sku": p["sku"], "customer_id": o["cust"]["customer_id"],
                    "order_id": o["order_id"], "rating": r, "text": random.choice(texts[r]),
                    "verified_purchase": True,
                    "tags": random.sample(tags_pool[r], k=int(rng.integers(1, len(tags_pool[r]) + 1))),
                    "review_ts": ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
                rid += 1
    for _ in range(400):  # unverified drive-by reviews
        p = by_sku[random.choice(list(by_sku))]
        r = int(np.clip(round(rng.normal(p["_quality"] - 0.3, 1.2)), 1, 5))
        reviews.append({"review_id": f"R{rid:07d}", "sku": p["sku"], "customer_id": None, "order_id": None,
                        "rating": r, "text": random.choice(texts[r]), "verified_purchase": False,
                        "tags": random.sample(tags_pool[r], k=1),
                        "review_ts": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")})
        rid += 1
    with open(RAW / "reviews.json", "w") as f:
        json.dump(reviews, f)

    # ---------- web events ----------
    events = []
    checkout_p = {"desktop": 0.62, "tablet": 0.52, "mobile": 0.38}
    span = (END - START).days
    for s in range(25000):
        device = random.choices(["mobile", "desktop", "tablet"], weights=[60, 32, 8])[0]
        t = datetime.combine(START + timedelta(days=int(rng.integers(0, span))), datetime.min.time(), tzinfo=timezone.utc) \
            + timedelta(seconds=int(rng.integers(6 * 3600, 23 * 3600)))
        sid = f"S{s:07d}"
        def ev(kind):
            nonlocal t
            t += timedelta(seconds=int(rng.integers(5, 240)))
            events.append({"session_id": sid, "event_type": kind, "device": device,
                           "event_ts": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "page": random.choice(["/", "/groceries", "/homeware", "/offers", "/product"])})
        for _ in range(int(rng.integers(1, 7))):
            ev("page_view")
        if rng.random() < 0.45:
            ev("add_to_basket")
            if rng.random() < checkout_p[device]:
                ev("checkout")
    with open(RAW / "events.json", "w") as f:
        json.dump(events, f)

    print(f"orders.csv        {len(orders):>7} rows (incl. dirty rows)")
    print(f"order_items.csv   {len(order_items):>7} rows")
    print(f"customers.json    {len(cust_out):>7} rows")
    print(f"products.csv      {len(products):>7} rows")
    print(f"reviews.json      {len(reviews):>7} docs")
    print(f"events.json       {len(events):>7} docs")
    print(f"customers_update  {len(movers):>7} movers (for SCD2 snapshot)")


if __name__ == "__main__":
    main()
