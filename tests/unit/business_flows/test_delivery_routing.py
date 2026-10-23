import pytest

from application.business_flows import delivery_routing as dr

TG = {"id": "t", "platform": "telegram", "type": "telegram_shared_bot", "external_account_id": "7", "status": "paused"}
VK = {"id": "v", "platform": "vk", "status": "active"}


def test_shared_activates_or_proposes_without_creating():
    c, f = dr.shared_telegram_connection([TG], 7)
    assert c["status"] == "active" and f[0]["step"] == "connection_activated"
    c, f = dr.shared_telegram_connection([], 7)
    assert f[0]["step"] == "connection_proposed" and c["credential_ref"].startswith("vault:")


def test_managed_preferred_and_ambiguity():
    m = {"id": "m", "platform": "telegram", "status": "active"}
    bots = [{"id": "b1", "platform": "telegram", "status": "active", "connection_id": "m"}]
    assert dr.preferred_telegram_connection([TG, m], bots, 7)[0]["id"] == "m"
    with pytest.raises(ValueError):
        dr.managed_telegram_connection([m, {**m, "id": "m2"}], [*bots, {**bots[0], "id": "b2", "connection_id": "m2"}])
    with pytest.raises(ValueError):
        dr.single_active_native_connection([VK, {**VK, "id": "v2"}], "vk")


def test_route_prefers_latest_contact_and_skips_unconnected():
    ids = [
        {"id": "1", "platform": "max", "last_contact_at": "2026-10-23"},
        {"id": "2", "platform": "vk", "last_contact_at": "2026-10-22"},
        {"id": "3", "platform": "email", "last_contact_at": "2026-10-24"},
    ]
    r = dr.preferred_customer_delivery_route(ids, [VK], [], 7)
    assert r.identity["id"] == "2" and r.connection["id"] == "v"
    with pytest.raises(ValueError):
        dr.preferred_customer_delivery_route(ids[:1], [VK], [], 7)


def test_statuses_and_summary():
    assert dr.connection_statuses([VK, {**TG, "credential_ref": "vault:x"}]) == [
        ("telegram", "paused"),
        ("vk", "active"),
    ]
    s = dr.delivery_summary(
        customers=[{"status": "active"}],
        programs=[],
        outbox=[{"status": "retry"}, {"status": "sent"}, {"status": "dead"}],
    )
    assert (s.customers, s.programs, s.dispatch_pending, s.dispatch_sent, s.dispatch_attention) == (1, 0, 1, 1, 1)
