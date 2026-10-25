"""
Module 5 - aggregation pipelines over reviews and events.

    python -m mongo.pipelines
"""
from __future__ import annotations

from mongo.mongo_load import get_db

# 1. Average rating per product, worst first (only products with enough reviews to trust)
AVG_RATING_PER_PRODUCT = [
    {"$group": {"_id": "$sku",
                "name": {"$first": "$product.name"},
                "category": {"$first": "$product.category"},
                "avg_rating": {"$avg": "$rating"},
                "reviews": {"$sum": 1}}},
    {"$match": {"reviews": {"$gte": 20}}},
    {"$sort": {"avg_rating": 1}},
    {"$limit": 10},
]

# 2. Basket abandonment by device: sessions that added to basket but never checked out
BASKET_ABANDONMENT_BY_DEVICE = [
    {"$group": {"_id": "$session_id",
                "device": {"$first": "$device"},
                "added": {"$max": {"$cond": [{"$eq": ["$event_type", "add_to_basket"]}, 1, 0]}},
                "checked_out": {"$max": {"$cond": [{"$eq": ["$event_type", "checkout"]}, 1, 0]}}}},
    {"$match": {"added": 1}},
    {"$group": {"_id": "$device",
                "basket_sessions": {"$sum": 1},
                "checkouts": {"$sum": "$checked_out"}}},
    {"$project": {"basket_sessions": 1, "checkouts": 1,
                  "abandonment_rate": {"$subtract": [1, {"$divide": ["$checkouts", "$basket_sessions"]}]}}},
    {"$sort": {"abandonment_rate": -1}},
]

# 3. What do unhappy customers complain about? Unwind the tags array on 1-2 star reviews
COMPLAINT_TAGS = [
    {"$match": {"rating": {"$lte": 2}}},
    {"$unwind": "$tags"},
    {"$group": {"_id": "$tags", "mentions": {"$sum": 1}}},
    {"$sort": {"mentions": -1}},
]

# 4. Ratings by category, verified purchases only
RATING_BY_CATEGORY = [
    {"$match": {"verified_purchase": True}},
    {"$group": {"_id": "$product.category", "avg_rating": {"$avg": "$rating"}, "reviews": {"$sum": 1},
                "one_star": {"$sum": {"$cond": [{"$eq": ["$rating", 1]}, 1, 0]}}}},
    {"$sort": {"avg_rating": 1}},
]


def run(db=None) -> dict[str, list[dict]]:
    db = db if db is not None else get_db()
    return {
        "avg_rating_per_product": list(db.reviews.aggregate(AVG_RATING_PER_PRODUCT)),
        "basket_abandonment_by_device": list(db.events.aggregate(BASKET_ABANDONMENT_BY_DEVICE)),
        "complaint_tags": list(db.reviews.aggregate(COMPLAINT_TAGS)),
        "rating_by_category": list(db.reviews.aggregate(RATING_BY_CATEGORY)),
    }


if __name__ == "__main__":
    for name, rows in run().items():
        print(f"\n== {name} ==")
        for r in rows:
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
