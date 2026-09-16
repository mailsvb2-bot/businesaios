from __future__ import annotations

import pytest

from application.risk import RiskHistoryInvariantViolation, RiskProjector, RiskRegistry
from contracts.event_store import BusinessFactV1
from contracts.risk import RiskLevel, RiskLifecycleStatus
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _registry(events=None):
    events = events or MemoryEventStore()
    return RiskRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_risk_registry_persists_idempotent_lifecycle() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="t", business_id="b", risk_id="r1", idempotency_key="create",
        risk_type="vendor_dependency", level=RiskLevel.HIGH,
        subject_kind="provider", subject_id="provider-1", occurred_at_ms=100,
    )
    replay = registry.create(
        tenant_id="t", business_id="b", risk_id="r1", idempotency_key="create",
        risk_type="vendor_dependency", level=RiskLevel.HIGH,
        subject_kind="provider", subject_id="provider-1", occurred_at_ms=100,
    )
    assert replay == created
    assert len(list(events.iter_events(tenant_id="t", start_ms=0))) == 1
    updated = registry.update_level(
        tenant_id="t", business_id="b", risk_id="r1", idempotency_key="raise",
        level=RiskLevel.CRITICAL, occurred_at_ms=110,
    )
    assert updated.level is RiskLevel.CRITICAL
    replay_after_update = registry.create(
        tenant_id="t", business_id="b", risk_id="r1", idempotency_key="create",
        risk_type="vendor_dependency", level=RiskLevel.HIGH,
        subject_kind="provider", subject_id="provider-1", occurred_at_ms=100,
    )
    assert replay_after_update.level is RiskLevel.CRITICAL
    assert len(list(events.iter_events(tenant_id="t", start_ms=0))) == 2
    with pytest.raises(ValueError, match="original durable mutation"):
        registry.create(
            tenant_id="t", business_id="b", risk_id="r1", idempotency_key="second-create",
            risk_type="vendor_dependency", level=RiskLevel.CRITICAL,
            subject_kind="provider", subject_id="provider-1", occurred_at_ms=110,
        )
    closed = registry.close(
        tenant_id="t", business_id="b", risk_id="r1", idempotency_key="close", occurred_at_ms=120,
    )
    assert closed.lifecycle_status is RiskLifecycleStatus.CLOSED
    assert closed.closed_at_ms == 120
    replay_after_close = registry.create(
        tenant_id="t", business_id="b", risk_id="r1", idempotency_key="create",
        risk_type="vendor_dependency", level=RiskLevel.HIGH,
        subject_kind="provider", subject_id="provider-1", occurred_at_ms=100,
    )
    assert replay_after_close.lifecycle_status is RiskLifecycleStatus.CLOSED
    with pytest.raises(ValueError, match="closed risk"):
        registry.update_level(
            tenant_id="t", business_id="b", risk_id="r1", idempotency_key="late",
            level=RiskLevel.LOW, occurred_at_ms=130,
        )


def test_risk_identity_relation_is_immutable_and_timestamp_is_strict() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="t", business_id="b", risk_id="r1", idempotency_key="create",
        risk_type="vendor_dependency", level="high", subject_kind="provider", subject_id="provider-1",
        occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="different identity metadata"):
        registry.create(
            tenant_id="t", business_id="b", risk_id="r1", idempotency_key="other",
            risk_type="vendor_dependency", level="high", subject_kind="provider", subject_id="provider-2",
            occurred_at_ms=100,
        )
    with pytest.raises(ValueError, match="cannot move backwards"):
        registry.update_level(
            tenant_id="t", business_id="b", risk_id="r1", idempotency_key="backwards",
            level="critical", occurred_at_ms=99,
        )


def test_risk_history_rejects_wrong_source_and_schema() -> None:
    wrong_source = MemoryEventStore()
    wrong_source.append_event(
        BusinessFactV1(
            fact_id="risk:bad", tenant_id="t", business_id="b", fact_type="risk.created",
            entity_id="r1", event_time_ms=100, observed_at_ms=100, source="other_writer",
            payload={
                "schema_version": 1, "risk_type": "vendor_dependency", "level": "high",
                "subject_kind": None, "subject_id": None,
            },
        ).as_event()
    )
    with pytest.raises(RiskHistoryInvariantViolation, match="canonical risk_registry"):
        RiskProjector(wrong_source).get(tenant_id="t", business_id="b", risk_id="r1")

    bad_schema = MemoryEventStore()
    bad_schema.append_event(
        BusinessFactV1(
            fact_id="risk:bad-schema", tenant_id="t", business_id="b", fact_type="risk.created",
            entity_id="r1", event_time_ms=100, observed_at_ms=100, source="risk_registry",
            payload={
                "schema_version": 999, "risk_type": "vendor_dependency", "level": "high",
                "subject_kind": None, "subject_id": None,
            },
        ).as_event()
    )
    with pytest.raises(RiskHistoryInvariantViolation, match="unsupported schema_version"):
        RiskProjector(bad_schema).get(tenant_id="t", business_id="b", risk_id="r1")


def test_risk_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "risk.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = RiskRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(
            tenant_id="tenant", business_id="business", risk_id="risk", idempotency_key="create",
            risk_type="cash_concentration", level="medium", subject_kind="asset", subject_id="asset-1",
            occurred_at_ms=100,
        )
        registry.update_level(
            tenant_id="tenant", business_id="business", risk_id="risk", idempotency_key="raise",
            level="high", occurred_at_ms=200,
        )
    with SqliteEventStore(str(path)) as events:
        restored = RiskProjector(events).get(
            tenant_id="tenant", business_id="business", risk_id="risk"
        )
    assert restored.risk_type == "cash_concentration"
    assert restored.level is RiskLevel.HIGH
    assert restored.subject_kind == "asset"
    assert restored.subject_id == "asset-1"


def test_risk_contract_rejects_partial_subject_relation() -> None:
    registry, _ = _registry()
    with pytest.raises(ValueError, match="must be set together"):
        registry.create(
            tenant_id="t", business_id="b", risk_id="r", idempotency_key="create",
            risk_type="dependency", level="low", subject_kind="provider", subject_id=None,
            occurred_at_ms=1,
        )
