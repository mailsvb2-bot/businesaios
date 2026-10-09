from __future__ import annotations

import pytest

from application.business_autonomy.support_case_registry import SupportCaseRegistry
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _store():
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    return events, claims, SupportCaseRegistry(event_store=events, idempotency_store=claims)


def _create(store, *, tenant_id="tenant-a", business_id="business-a",
            actor_id="owner", summary="Messages are not arriving", key="new-case"):
    return store.create(
        tenant_id=tenant_id, business_id=business_id, actor_id=actor_id,
        category="integration", summary=summary, idempotency_key=key,
    )


def _transition(store, case, action, *, operator_id="support-1", key=None):
    return store.transition(
        tenant_id="tenant-a", business_id="business-a", case_id=case["id"],
        operator_id=operator_id, action=action,
        expected_revision=case["revision"], idempotency_key=key or action + "-1",
    )


def test_support_journey_is_durable_and_scoped_through_canonical_events():
    events, claims, registry = _store()
    created = _create(registry)
    assert created["status"] == "open" and created["revision"] == 1
    assert len(events) == 1
    assert _create(registry) == created and len(events) == 1
    claim = _transition(registry, created, "claim")
    assert claim["status"] == "claimed" and claim["claimed_by_operator_user_id"] == "support-1"
    assert claim["revision"] == 2
    assert len(events) == 2
    assert _transition(registry, created, "claim") == claim
    assert len(events) == 2
    with pytest.raises(RuntimeError, match="not_claimed_by_operator"):
        _transition(registry, claim, "resolve", operator_id="support-2")
    released = _transition(registry, claim, "release")
    assert released["status"] == "open" and released["claimed_by_operator_user_id"] is None
    again = _transition(registry, released, "claim", key="claim-2")
    resolved = _transition(registry, again, "resolve")
    assert resolved["status"] == "resolved" and resolved["revision"] == 5
    with pytest.raises(RuntimeError, match="revision_conflict"):
        _transition(registry, created, "claim", key="claim-3")
    with pytest.raises(RuntimeError, match="not_open"):
        _transition(registry, resolved, "claim", key="claim-4")
    assert registry.list(tenant_id="tenant-a", business_id="business-a") == [resolved]
    # Simulate a process restart on the same canonical stores.
    restored = SupportCaseRegistry(event_store=events, idempotency_store=claims)
    assert restored.get(tenant_id="tenant-a", business_id="business-a", case_id=created["id"]) == resolved


def test_support_rejects_tenant_business_and_idempotency_confusion():
    events, claims, registry = _store()
    created = _create(registry)
    with pytest.raises(KeyError):
        registry.get(tenant_id="tenant-b", business_id="business-a", case_id=created["id"])
    with pytest.raises(KeyError):
        registry.get(tenant_id="tenant-a", business_id="business-b", case_id=created["id"])
    assert registry.list(tenant_id="tenant-b", business_id="business-a") == []
    assert registry.list(tenant_id="tenant-a", business_id="business-b") == []
    with pytest.raises(RuntimeError, match="idempotency_conflict"):
        _create(registry, summary="Different topic", key="new-case")
    with pytest.raises(ValueError, match="credentials"):
        _create(registry, summary="api_key: abcdefghijklmnopqrstuvwxyz", key="new-secret")
    assert len(events) == 1
    with pytest.raises(ValueError, match="revision"):
        registry.transition(tenant_id="tenant-a", business_id="business-a", case_id=created["id"],
                            operator_id="support-1", action="claim", expected_revision=True,
                            idempotency_key="claim-invalid")
    with pytest.raises(ValueError, match="limit"):
        registry.list(tenant_id="tenant-a", business_id="business-a", limit=1000)
    assert len(events) == 1


def test_support_different_tenants_reusing_client_operation_keys_are_isolated():
    events, claims, registry = _store()
    first = _create(registry)
    second = _create(registry, tenant_id="tenant-b")
    third = _create(registry, business_id="business-b")
    assert len({first["id"], second["id"], third["id"]}) == 3
    assert len(events) == 3
    assert len(registry.list(tenant_id="tenant-a", business_id="business-a")) == 1
    # Both businesses can independently claim their cases with exactly the
    # same client-generated key, using the same tenant-wide canonical store.
    first_claimed = registry.transition(
        tenant_id="tenant-a", business_id="business-a", case_id=first["id"],
        operator_id="shared-support-agent", action="claim",
        expected_revision=first["revision"], idempotency_key="claim-1",
    )
    third_claimed = registry.transition(
        tenant_id="tenant-a", business_id="business-b", case_id=third["id"],
        operator_id="shared-support-agent", action="claim",
        expected_revision=third["revision"], idempotency_key="claim-1",
    )
    assert first_claimed["status"] == third_claimed["status"] == "claimed"
    assert first_claimed["id"] != third_claimed["id"]
    assert len(events) == 5
    # Replay is scoped to the individual case and remains exactly-once.
    assert registry.transition(
        tenant_id="tenant-a", business_id="business-b", case_id=third["id"],
        operator_id="shared-support-agent", action="claim",
        expected_revision=third["revision"], idempotency_key="claim-1",
    ) == third_claimed
    assert len(events) == 5
    with pytest.raises(RuntimeError, match="idempotency_conflict"):
        registry.transition(
            tenant_id="tenant-a", business_id="business-b", case_id=third["id"],
            operator_id="shared-support-agent", action="claim",
            expected_revision=third["revision"] + 1, idempotency_key="claim-1",
        )
    assert len(events) == 5



def test_support_owner_reusing_request_key_is_scoped_to_actor_within_business():
    events, claims, registry = _store()
    first = _create(registry, actor_id="owner-one")
    second = _create(registry, actor_id="owner-two")
    assert first["id"] != second["id"]
    assert first["created_by_member_id"] == "owner-one"
    assert second["created_by_member_id"] == "owner-two"
    assert len(events) == 2
    assert len(registry.list(tenant_id="tenant-a", business_id="business-a")) == 2


def test_owner_history_is_derived_from_canonical_events_and_scrubs_privileged_metadata():
    events, claims, registry = _store()
    created = _create(registry)
    claimed = _transition(registry, created, "claim")
    released = _transition(registry, claimed, "release")
    claimed_again = _transition(registry, released, "claim", key="claim-again")
    resolved = _transition(registry, claimed_again, "resolve")
    observed = registry.history(
        tenant_id="tenant-a", business_id="business-a", case_id=created["id"],
    )
    assert observed["case_id"] == created["id"]
    assert observed["revision"] == 5 and observed["total"] == 5
    assert observed["truncated"] is False
    assert [entry["action"] for entry in observed["entries"]] == [
        "created", "claimed", "released", "claimed", "resolved",
    ]
    assert [entry["revision"] for entry in observed["entries"]] == [1, 2, 3, 4, 5]
    assert all(entry["occurred_at"] for entry in observed["entries"])
    assert all(set(entry) == {"revision", "action", "status", "occurred_at"} for entry in observed["entries"])
    assert "support-1" not in str(observed)
    assert "claim-again" not in str(observed)
    page = registry.history(
        tenant_id="tenant-a", business_id="business-a", case_id=created["id"], limit=2,
    )
    assert page["total"] == 5 and page["truncated"] is True
    assert [entry["revision"] for entry in page["entries"]] == [4, 5]
    assert registry.get(tenant_id="tenant-a", business_id="business-a", case_id=created["id"]) == resolved
    for tenant, business in [("tenant-b", "business-a"), ("tenant-a", "business-b")]:
        with pytest.raises(KeyError):
            registry.history(tenant_id=tenant, business_id=business, case_id=created["id"])
    for invalid_limit in (0, 101, True, "5"):
        with pytest.raises(ValueError, match="limit"):
            registry.history(
                tenant_id="tenant-a", business_id="business-a",
                case_id=created["id"], limit=invalid_limit,
            )
    restarted = SupportCaseRegistry(event_store=events, idempotency_store=claims)
    assert restarted.history(tenant_id="tenant-a", business_id="business-a", case_id=created["id"]) == observed
