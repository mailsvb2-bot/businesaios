from zoneinfo import ZoneInfo

import pytest

from application.business_flows import promotion_attribution as pa

MSK = ZoneInfo("Europe/Moscow")


def test_window_is_local_days_in_utc():
    s, u = pa.event_window("2026-10-01", "2026-10-01", zone=MSK)
    assert s.isoformat() == "2026-09-30T21:00:00+00:00" and u.isoformat() == "2026-10-01T21:00:00+00:00"
    with pytest.raises(ValueError):
        pa.event_window("2026-10-02", "2026-10-01", zone=MSK)
    with pytest.raises(ValueError):
        pa.event_window("x", "2026-10-01", zone=MSK)


def test_exact_attribution_without_cross_credit():
    s, u = pa.event_window("2026-10-01", "2026-10-31", zone=MSK)
    T = "2026-10-10T10:00:00+00:00"
    bk = [
        (T, {"step": "promotion_saved", "promotion_id": "p1", "source_token": "tok1", "offering_id": "o1"}),
        (T, {"step": "promotion_saved", "promotion_id": "p2", "source_token": "tok2"}),
        (T, {"step": "promotion_opened", "promotion_id": "p1", "customer_id": "a"}),
        ("2026-10-11T10:00:00+00:00", {"step": "booked", "promotion_id": "p1", "customer_id": "b"}),
        ("2026-10-11T10:00:00+00:00", {"step": "booked", "promotion_id": "p2", "customer_id": "c"}),
        ("2026-11-05T10:00:00+00:00", {"step": "promotion_opened", "promotion_id": "p1", "customer_id": "z"}),
    ]
    sales = [
        (T, {"step": "lead_inbound", "lead_id": "L1", "customer_id": "b", "offering_id": "o1"}),
        (T, {"step": "lead_inbound", "lead_id": "L2", "customer_id": "c"}),
        ("2026-10-12T10:00:00+00:00", {"step": "lead_event", "lead_id": "L1", "stage": "won"}),
        ("2026-10-10T09:00:00+00:00", {"step": "lead_event", "lead_id": "L2", "stage": "won"}),  # before booking
    ]
    r = pa.attribute(bk, sales, campaign_ids={"p1", "p2"}, start=s, until=u)
    assert r.leads == {"p1": {"a", "b"}, "p2": {"c"}}
    assert r.bookings == {"p1": {"b"}, "p2": {"c"}}
    assert r.won == {"p1": {"b"}} and r.source_won == {"tok1": {"b"}}
    assert r.source_bookings == {"tok1": {"b"}, "tok2": {"c"}}
    assert pa.attribute(bk, sales, campaign_ids={"p2"}, start=s, until=u).won == {}
    assert pa.attribute(bk, sales, campaign_ids=set(), start=s, until=u).leads == {}
