from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from application.business_flows import customer_menu as cm
from application.business_flows import event_channels as ec
from application.business_flows import public_events as pe
from crm.customer_registry import CustomerRegistry
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault

NOW = datetime(2026, 10, 1, tzinfo=UTC)


def _board():
    f = [{"step": "pub_event_created", "event_id": "e1", "title": "T", "kind": "webinar",
          "starts_at": (NOW + timedelta(days=3)).isoformat(), "timezone": "Europe/Moscow", "slug": "s",
          "provider_key": "zoom", "join_url": "https://z"},
         {"step": "pub_event_status", "event_id": "e1", "status": "published"}]
    fact, _ = pe.register(pe.replay(f), slug="s", name="Анна", email="A@x.ru", consent=True, now=NOW)
    return f + [fact], fact["registration_id"]


def test_actor_prefers_creator_then_role_order():
    ms = [{"member_id": "m3", "role": "support", "status": "active", "created_at": "1"},
          {"member_id": "m2", "role": "manager", "status": "active", "created_at": "1"},
          {"member_id": "m1", "role": "owner", "status": "revoked", "created_at": "0"},
          {"member_id": "m4", "role": "viewer", "status": "active", "created_at": "0"}]
    assert pe.automation_actor(ms, business_active=True, created_by_member_id="m3")["member_id"] == "m3"
    assert pe.automation_actor(ms, business_active=True, created_by_member_id="m1")["member_id"] == "m2"
    assert pe.automation_actor(ms, business_active=False, created_by_member_id="m3") is None
    assert pe.automation_actor(ms[3:], business_active=True, created_by_member_id=None) is None


def test_projection_is_idempotent_never_merges_phone_and_feeds_reminder_links():
    f, rid = _board()
    reg = CustomerRegistry(event_store=MemoryEventStore(), idempotency_store=InMemoryIdempotencyStore(),
                           pii_vault=InMemorySecretVault())
    actor = {"member_id": "m1", "role": "owner"}
    other = reg.ensure_customer_identity(tenant_id="t", business_id="b", channel="phone", external_subject="+7 900 000 0000")
    b = pe.replay(f)
    with pytest.raises(PermissionError):
        pe.attach_registration_to_customer(reg, b, rid, tenant_id="t", business_id="b", email="z@x.ru", actor=actor)
    assert pe.attach_registration_to_customer(reg, b, rid, tenant_id="t", business_id="b", email="a@x.ru", actor=None) == (None, [])
    cid, facts = pe.attach_registration_to_customer(reg, b, rid, tenant_id="t", business_id="b", email="a@x.ru",
                                                    actor=actor, phone="+79000000000")
    assert cid != other.customer.customer_id and facts[0]["phone_linked"] is False
    assert pe.attach_registration_to_customer(reg, b, rid, tenant_id="t", business_id="b", email="a@x.ru", actor=actor)[0] == cid
    b = pe.replay(f + facts)
    assert b.registrations[rid].customer_id == cid
    tokens, fact = ec.issue_for_registration(b, rid, now_ms=0, skip_platforms=("vk",))
    assert set(tokens) == {"telegram", "max"} and fact["registration_id"] == rid
    assert ec.issue_for_registration(pe.replay(f), rid, now_ms=0) == ({}, None)
    v = ec.consume([fact], {}, token=tokens["max"], platform="max", external_subject="u1", now_ms=1,
                   registrations=b.registrations)
    assert v["registration_id"] == rid and v["customer_id"] == cid
    with pytest.raises(ec.LinkRejected):
        ec.consume([fact, v], {}, token=tokens["max"], platform="max", external_subject="u1", now_ms=1,
                   registrations=b.registrations)
    with pytest.raises(ec.LinkRejected):
        ec.consume([fact], {}, token=tokens["telegram"], platform="telegram", external_subject="u", now_ms=1)


def test_uuid_callback_tokens_roundtrip():
    u = str(uuid4())
    t = cm.uuid_token(u)
    assert len(t) == 22 and cm.token_uuid(t) == u
