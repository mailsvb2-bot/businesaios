from __future__ import annotations

import pytest

from application.business_autonomy.registry import AgentIdentityRegistry
from application.business_autonomy.contracts import AgentLifecycleStatus
from reliability.idempotency_store import InMemoryIdempotencyStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms=None,
        user_id=None,
        event_type=None,
    ):
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if int(event.get("timestamp_ms") or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)


def _registry():
    events = MemoryEventStore()
    return AgentIdentityRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
    ), events


def test_agent_identity_delegation_cannot_widen_parent_authority() -> None:
    registry, _ = _registry()
    root = registry.register(
        tenant_id="tenant",
        business_id="business",
        agent_id="business-agent",
        idempotency_key="root",
        agent_type="business",
        agent_version="v1",
        capability_scope=("send_email", "launch_campaign"),
        budget_scope={"messages_per_day": 100.0, "spend_minor": 50_000.0},
        risk_scope=("low", "medium"),
        data_scope=("customers", "campaigns"),
        occurred_at_ms=100,
    )
    assert root.lifecycle_status is AgentLifecycleStatus.ACTIVE

    child = registry.register(
        tenant_id="tenant",
        business_id="business",
        agent_id="marketing-agent",
        idempotency_key="child",
        agent_type="marketing",
        agent_version="v1",
        delegated_by="business-agent",
        capability_scope=("launch_campaign",),
        budget_scope={"spend_minor": 10_000.0},
        risk_scope=("low",),
        data_scope=("campaigns",),
        occurred_at_ms=200,
    )
    assert child.delegated_by == "business-agent"

    with pytest.raises(ValueError, match="capability_scope exceeds"):
        registry.register(
            tenant_id="tenant",
            business_id="business",
            agent_id="bad-capability",
            idempotency_key="bad-capability",
            agent_type="marketing",
            agent_version="v1",
            delegated_by="business-agent",
            capability_scope=("refund_payment",),
            occurred_at_ms=300,
        )

    with pytest.raises(ValueError, match="budget_scope exceeds"):
        registry.register(
            tenant_id="tenant",
            business_id="business",
            agent_id="bad-budget",
            idempotency_key="bad-budget",
            agent_type="marketing",
            agent_version="v1",
            delegated_by="business-agent",
            capability_scope=("launch_campaign",),
            budget_scope={"spend_minor": 60_000.0},
            occurred_at_ms=300,
        )

    with pytest.raises(ValueError, match="data_scope exceeds"):
        registry.register(
            tenant_id="tenant",
            business_id="business",
            agent_id="bad-data",
            idempotency_key="bad-data",
            agent_type="marketing",
            agent_version="v1",
            delegated_by="business-agent",
            capability_scope=("launch_campaign",),
            data_scope=("payments",),
            occurred_at_ms=300,
        )


def test_agent_identity_replay_revocation_and_parent_revocation_fail_closed() -> None:
    registry, events = _registry()
    root = registry.register(
        tenant_id="tenant",
        business_id="business",
        agent_id="root",
        idempotency_key="root-create",
        agent_type="business",
        agent_version="v1",
        capability_scope=("send_email",),
        budget_scope={"messages_per_day": 20.0},
        risk_scope=("low",),
        data_scope=("customers",),
        occurred_at_ms=100,
    )
    count = len(events.events)
    assert registry.register(
        tenant_id="tenant",
        business_id="business",
        agent_id="root",
        idempotency_key="root-create",
        agent_type="business",
        agent_version="v1",
        capability_scope=("send_email",),
        budget_scope={"messages_per_day": 20.0},
        risk_scope=("low",),
        data_scope=("customers",),
        occurred_at_ms=999,
    ) == root
    assert len(events.events) == count

    revoked = registry.revoke(
        tenant_id="tenant",
        business_id="business",
        agent_id="root",
        idempotency_key="root-revoke",
        occurred_at_ms=200,
    )
    assert revoked.lifecycle_status is AgentLifecycleStatus.REVOKED
    with pytest.raises(PermissionError, match="revoked"):
        registry.assert_active(
            tenant_id="tenant",
            business_id="business",
            agent_id="root",
        )
    with pytest.raises(ValueError, match="delegating parent agent is revoked"):
        registry.register(
            tenant_id="tenant",
            business_id="business",
            agent_id="late-child",
            idempotency_key="late-child",
            agent_type="worker",
            agent_version="v1",
            delegated_by="root",
            occurred_at_ms=300,
        )


def test_agent_identity_scope_is_tenant_and_business_isolated() -> None:
    registry, _ = _registry()
    registry.register(
        tenant_id="tenant-a",
        business_id="business-a",
        agent_id="root",
        idempotency_key="root-a",
        agent_type="business",
        agent_version="v1",
        capability_scope=("send_email",),
        occurred_at_ms=100,
    )
    with pytest.raises(LookupError):
        registry.get(
            tenant_id="tenant-a",
            business_id="business-b",
            agent_id="root",
        )
    with pytest.raises(LookupError):
        registry.get(
            tenant_id="tenant-b",
            business_id="business-a",
            agent_id="root",
        )
