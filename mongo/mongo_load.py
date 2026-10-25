"""
Module 5 - load reviews and clickstream events into MongoDB as documents.

    python -m mongo.mongo_load

reviews: one document per review, with the product's name/category embedded
         (a snapshot at review time) and a tags array.
events:  one document per clickstream event (page_view, add_to_basket, checkout).
Re-runnable: both collections are dropped and rebuilt.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BATCH = 5000

REVIEW_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["sku", "rating", "verified_purchase", "tags", "review_ts"],
    "properties": {
        "sku": {"bsonType": "string"},
        "rating": {"bsonType": "int", "minimum": 1, "maximum": 5},
        "verified_purchase": {"bsonType": "bool"},
        "tags": {"bsonType": "array", "items": {"bsonType": "string"}},
        "review_ts": {"bsonType": "date"},
    },
}}
EVENT_TYPES = ("page_view", "add_to_basket", "checkout")


def get_db():
    load_dotenv(ROOT / ".env")
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    return client[os.getenv("MONGO_DB", "albion")]


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def review_docs() -> list[dict]:
    with open(RAW / "products.csv", newline="") as f:
        products = {p["sku"]: p for p in csv.DictReader(f)}
    with open(RAW / "reviews.json") as f:
        raw = json.load(f)
    docs = []
    for r in raw:
        p = products.get(r["sku"], {})
        docs.append({
            "_id": r["review_id"],
            "sku": r["sku"],
            "product": {"name": p.get("name"), "category": p.get("category")},   # embedded snapshot
            "customer_id": r["customer_id"],
            "order_id": r["order_id"],
            "rating": int(r["rating"]),
            "text": r["text"],
            "verified_purchase": bool(r["verified_purchase"]),
            "tags": list(r["tags"]),
            "review_ts": parse_utc(r["review_ts"]),
        })
    return docs


def event_docs() -> list[dict]:
    with open(RAW / "events.json") as f:
        raw = json.load(f)
    return [{**e, "event_ts": parse_utc(e["event_ts"])} for e in raw if e["event_type"] in EVENT_TYPES]


def insert_batched(coll, docs: list[dict]) -> None:
    for i in range(0, len(docs), BATCH):
        coll.insert_many(docs[i:i + BATCH], ordered=False)


def main() -> None:
    db = get_db()
    db.drop_collection("reviews")
    db.drop_collection("events")
    try:
        db.create_collection("reviews", validator=REVIEW_VALIDATOR)
    except Exception:                       # e.g. mongomock without validator support
        db.create_collection("reviews")

    insert_batched(db.reviews, review_docs())
    insert_batched(db.events, event_docs())

    db.reviews.create_index([("sku", ASCENDING)], name="ix_sku")
    db.reviews.create_index([("customer_id", ASCENDING)], name="ix_customer")
    db.events.create_index([("event_ts", DESCENDING)], name="ix_event_ts")
    db.events.create_index([("session_id", ASCENDING), ("event_ts", ASCENDING)], name="ix_session_ts")

    print(f"reviews: {db.reviews.count_documents({}):>7} docs  indexes={sorted(db.reviews.index_information())}")
    print(f"events:  {db.events.count_documents({}):>7} docs  indexes={sorted(db.events.index_information())}")


if __name__ == "__main__":
    main()
