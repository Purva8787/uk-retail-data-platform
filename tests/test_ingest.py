"""Unit tests for ingest.py type casting and the ingest summary."""
from datetime import datetime
from decimal import Decimal

import pytest

from ingestion.ingest import (normalise_postcode, postcode_area, read_orders, to_int, to_london_ts,
                              to_money)


def test_money_is_decimal_2dp():
    assert to_money("£49.99") == Decimal("49.99")
    assert to_money("10") == Decimal("10.00")
    assert to_money("1,234.5") == Decimal("1234.50")
    with pytest.raises(ValueError):
        to_money("abc")


def test_ids_are_int():
    assert to_int(" 1001 ") == 1001
    with pytest.raises(ValueError):
        to_int("")


def test_timestamps_become_europe_london():
    winter = to_london_ts("2024-01-15 10:00:00")
    assert str(winter.tzinfo) == "Europe/London" and winter.utcoffset().total_seconds() == 0
    summer = to_london_ts("2024-07-01T09:00:00Z")          # 09:00 UTC = 10:00 BST
    assert summer.hour == 10 and summer.utcoffset().total_seconds() == 3600
    with pytest.raises(ValueError):
        to_london_ts("31/02/2024 25:61")


def test_postcode_helpers():
    assert normalise_postcode("sw1a1aa") == "SW1A 1AA"
    assert postcode_area("SW1A 1AA") == "SW"
    assert postcode_area("G12 8QQ") == "G"
    assert normalise_postcode("SW1") is None


def test_read_orders_catches_duplicates(tmp_path):
    f = tmp_path / "orders.csv"
    f.write_text(
        "order_id,customer_id,order_ts,postcode,total_gbp,vat_gbp,channel\n"
        "1,10,2024-03-01 09:00:00,SW1A 1AA,£49.99,8.33,web\n"
        "1,10,2024-03-01 09:00:00,SW1A 1AA,£49.99,8.33,web\n"
        "2,,2024-03-01 09:00:00,SW1A 1AA,10.00,0,web\n"
        "3,11,not-a-date,M1 1AE,10.00,0,app\n", encoding="utf-8")
    rows, s = read_orders(f, area_map={"SW": {"region": "London", "nation": "England"}})
    assert (s.rows_read, s.rows_clean, s.duplicated, s.rejected) == (4, 1, 1, 2)
    assert rows[0]["total_gbp"] == Decimal("49.99") and rows[0]["region"] == "London"
    assert isinstance(rows[0]["order_ts"], datetime)
