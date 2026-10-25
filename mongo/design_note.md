# Design note: when documents beat tables

## What we put where

| Data | Store | Why |
|---|---|---|
| Orders, order items, customers, products | PostgreSQL | Money and tax. We need foreign keys, `CHECK (total_gbp >= 0)`, transactions and exact `NUMERIC` maths. A half-written order must be impossible. |
| Reviews | MongoDB | Each review is self-contained, has a variable-length `tags` array and free text, and is read as a whole. Its shape will change (photos, helpful-votes, replies) without a migration. |
| Web events | MongoDB | High-volume, append-only, written once, never updated. Different event types will carry different fields (search terms, basket value) and we don't want a wide sparse table. |

## Review document shape

```json
{
  "_id": "R0000123",
  "sku": "AB-10085",
  "product": {"name": "Albion Farmhouse Clotted Cream Fudge", "category": "Snacks & Confectionery"},
  "customer_id": 3025,
  "order_id": 103676,
  "rating": 2,
  "text": "Disappointing quality.",
  "verified_purchase": true,
  "tags": ["poor_quality", "small"],
  "review_ts": ISODate("2024-03-02T10:15:00Z")
}
```

**Embedded** `product` snapshot: the review page needs the product name without a join, and the name *at the time of review* is what the customer saw. The trade-off is that a renamed product leaves old names in old reviews, which is acceptable here.

**Referenced** `customer_id` / `order_id`: customer data is personal, changes, and is owned by PostgreSQL. Copying it into every review would spread PII and go stale.

**Array** `tags`: queried with `$unwind` to count complaints. In SQL this would be a separate `review_tags` table.

A `$jsonSchema` validator keeps `rating` between 1 and 5 and requires `sku`, so "schemaless" doesn't mean "anything goes".

## Events

One document per event, indexed on `event_ts` (time-range queries) and `(session_id, event_ts)` (rebuilding a session in order). At much higher volume we would switch to a MongoDB **time-series collection** or bucket events per session to cut index size.

## Indexes

- `reviews.sku`: every "rating per product" lookup and the `$group` in the pipeline.
- `reviews.customer_id`: joining reviews back to a customer's repeat behaviour.
- `events.event_ts`: daily/monthly funnels.
- `events.(session_id, event_ts)`: abandonment analysis.

## Rule of thumb

Choose **tables** when the data has relationships you must enforce, when you aggregate across it in many different ways, or when it's money. Choose **documents** when each record is read and written as one unit, when its shape varies or will evolve, and when you'd otherwise need several child tables just to hold lists.
