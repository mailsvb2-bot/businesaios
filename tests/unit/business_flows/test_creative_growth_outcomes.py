from datetime import UTC, date, datetime

import pytest

from application.business_flows import creative_growth_outcomes as cg

ENV = {"BAI_ANALYTICS_TIMEZONE": "Europe/Moscow"}
AT = int(datetime(2026, 10, 20, 12, tzinfo=UTC).timestamp() * 1000)


def test_period_bounds_and_zone():
    assert cg.period(7, date(2026, 10, 24)) == ("2026-10-18", "2026-10-24")
    with pytest.raises(ValueError):
        cg.period(0)
    with pytest.raises(RuntimeError):
        cg.analytics_zone({"BAI_ANALYTICS_TIMEZONE": "No/Zone"})


def test_variant_shared_unavailable_never_duplicated():
    trial = {"trial_id": "t1", "arms": [
        {"variant_id": "a", "promotion_campaign_id": "p1", "promotion_source_token": "ta"},
        {"variant_id": "b", "promotion_campaign_id": "p2"},
        {"variant_id": "c", "promotion_campaign_id": "p2"},
        {"variant_id": "d", "promotion_campaign_id": "p3"},
        {"variant_id": "e"}]}
    pay = [{"step": "promotion_opened", "promotion_id": "p1", "source_token": "ta", "customer_id": "x", "at_ms": AT},
           {"step": "booked", "promotion_id": "p1", "source_token": "ta", "customer_id": "x", "at_ms": AT},
           {"step": "promotion_opened", "promotion_id": "p2", "customer_id": "y", "at_ms": AT},
           {"step": "promotion_opened", "promotion_id": "p3", "customer_id": "z", "at_ms": AT},
           {"step": "promotion_opened", "promotion_id": "p3", "customer_id": "old", "at_ms": 0}]
    r = cg.get_creative_growth_outcomes(trial, pay, days=30, now=date(2026, 10, 24), env=ENV)
    v = {x["variant_id"]: x for x in r["variants"]}
    assert (v["a"]["leads"], v["a"]["bookings"], v["a"]["attribution_scope"]) == (1, 1, "variant")
    assert v["b"]["leads"] == v["c"]["leads"] == 0 and v["b"]["attribution_scope"] == "shared_campaign"
    assert v["d"]["leads"] == 1 and v["e"]["attribution_scope"] == "unavailable"
    assert r["shared_campaigns"][0]["leads"] == 1 and r["shared_campaigns"][0]["variant_ids"] == ("b", "c")
    assert r["variant_level_ready"] is False
    assert cg.variant_level_ready([{"attribution_scope": "variant"}]) and not cg.variant_level_ready([])


def test_recommendation_and_confirmed_cas_apply():
    from application.business_flows.creative_winner import CreativeWinnerApplyError

    trial = {"trial_id": "t2", "revision": 3, "status": "running", "arms": [
        {"variant_id": "a", "publication_job_id": "ja", "promotion_campaign_id": "pa", "allocation_bps": 5000},
        {"variant_id": "b", "publication_job_id": "jb", "promotion_campaign_id": "pb", "allocation_bps": 5000}]}
    pay = []
    for i in range(100):
        for pid in ("pa", "pb"):
            pay.append({"step": "promotion_opened", "promotion_id": pid, "customer_id": f"{pid}{i}", "at_ms": AT})
        if i < 40:
            pay.append({"step": "booked", "promotion_id": "pa", "customer_id": f"pa{i}", "at_ms": AT})
        if i < 5:
            pay.append({"step": "booked", "promotion_id": "pb", "customer_id": f"pb{i}", "at_ms": AT})
    kw = {"days": 30, "now": date(2026, 10, 24), "env": ENV}
    rec = cg.get_creative_growth_recommendation(trial, pay, **kw)
    assert rec["recommendation"]["status"] == "ready" and rec["recommendation"]["winner_variant_id"] == "a"
    with pytest.raises(CreativeWinnerApplyError):
        cg.apply_creative_growth_recommendation(trial, pay, rec, confirmed=False, **kw)
    fact = cg.apply_creative_growth_recommendation(trial, pay, rec, confirmed=True, **kw)
    assert fact["revision"] == 4 and fact["winner_variant_id"] == "a"
    with pytest.raises(CreativeWinnerApplyError):  # evidence changed after review
        cg.apply_creative_growth_recommendation(trial, pay[:-3], rec, confirmed=True, **kw)
    idle = cg.get_creative_growth_recommendation({**trial, "status": "paused"}, pay, **kw)
    assert idle["recommendation"]["status"] == "not_running"
