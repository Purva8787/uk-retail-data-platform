"""Unit tests for rules.py: 10 sample orders, including the edge cases."""
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import requests

from ingestion.ingest import normalise_postcode, postcode_area
from ingestion.rules import apply_rules, delivery_band, is_valid_uk_postcode, lookup_postcode

REGION = {"SW": "London", "IV": "Scotland", "HS": "Scotland", "KW": "Scotland", "ZE": "Scotland",
          "BT": "Northern Ireland", "KA": "Scotland", "CF": "Wales", "M": "North West"}


def order(oid, postcode, total):
    pc = normalise_postcode(postcode)
    area = postcode_area(pc)
    return {"order_id": oid, "postcode": pc, "postcode_area": area,
            "region": REGION.get(area), "total_gbp": Decimal(total)}


SAMPLE = [
    order(1, "SW1A 1AA", "500.00"),   # exactly £500 -> high value
    order(2, "M1 1AE", "499.99"),     # 1p under -> not high value
    order(3, "CF10 1EP", "40.00"),    # exactly £40 -> free delivery
    order(4, "CF10 1EP", "39.99"),    # 1p under -> pays delivery
    order(5, "IV2 3BW", "60.00"),     # Highlands -> surcharge even above £40
    order(6, "BT1 5GS", "25.00"),     # Northern Ireland
    order(7, "ze1 0lz", "12.00"),     # Shetland, lowercase/no-space input normalised
    order(8, "KA27 8AA", "45.00"),    # Arran (KA) is NOT in the surcharge list -> mainland
    order(9, "INVALID", "30.00"),     # bad postcode -> rejected
    order(10, "HS1 2AA", "-5.00"),    # negative total -> rejected
]


@pytest.fixture(scope="module")
def result():
    return apply_rules([dict(o) for o in SAMPLE])


def by_id(rows, oid):
    return next(r for r in rows if r["order_id"] == oid)


def test_valid_and_rejected_counts(result):
    valid, rejected = result
    assert len(valid) == 8
    assert {r["order_id"]: r["reason"] for r in rejected} == {9: "bad_postcode", 10: "negative_total"}


def test_high_value_boundary(result):
    valid, _ = result
    assert by_id(valid, 1)["is_high_value"] is True
    assert by_id(valid, 2)["is_high_value"] is False


def test_free_delivery_boundary(result):
    valid, _ = result
    assert by_id(valid, 3)["free_delivery"] is True and by_id(valid, 3)["delivery_fee_gbp"] == Decimal("0.00")
    assert by_id(valid, 4)["free_delivery"] is False and by_id(valid, 4)["delivery_fee_gbp"] == Decimal("3.99")


def test_delivery_bands(result):
    valid, _ = result
    assert by_id(valid, 5)["delivery_band"] == "highlands_islands"
    assert by_id(valid, 5)["delivery_fee_gbp"] == Decimal("5.95")
    assert by_id(valid, 6)["delivery_band"] == "northern_ireland"
    assert by_id(valid, 6)["delivery_fee_gbp"] == Decimal("8.94")
    assert by_id(valid, 7)["delivery_band"] == "highlands_islands"
    assert by_id(valid, 8)["delivery_band"] == "mainland"


@pytest.mark.parametrize("pc,ok", [("SW1A 1AA", True), ("EC1A 1BB", True), ("G1 1XQ", True),
                                   ("SW1A1AA", False), ("12345", False), ("", False), (None, False)])
def test_postcode_format(pc, ok):
    assert is_valid_uk_postcode(pc) is ok


def test_delivery_band_function():
    assert [delivery_band(a) for a in ("IV", "HS", "KW", "ZE", "BT", "SW", None)] == \
        ["highlands_islands"] * 4 + ["northern_ireland", "mainland", "mainland"]


def _resp(status, payload=None):
    r = MagicMock(status_code=status)
    r.json.return_value = payload or {}
    r.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(str(status))
    return r


def test_lookup_retries_then_succeeds():
    ok = _resp(200, {"result": {"postcode": "SW1A 1AA", "region": "London", "country": "England",
                                "admin_district": "Westminster"}})
    session = MagicMock()
    session.get.side_effect = [requests.ConnectionError("down"), _resp(503), ok]
    out = lookup_postcode("SW1A 1AA", session=session, backoff=0)
    assert out["local_authority"] == "Westminster"
    assert session.get.call_count == 3


def test_lookup_gives_up_after_three_attempts():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("down")
    assert lookup_postcode("SW1A 1AA", session=session, backoff=0) is None
    assert session.get.call_count == 3


def test_lookup_404_does_not_retry():
    session = MagicMock()
    session.get.return_value = _resp(404)
    assert lookup_postcode("ZZ1 1ZZ", session=session, backoff=0) is None
    assert session.get.call_count == 1
