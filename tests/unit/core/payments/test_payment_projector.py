from __future__ import annotations

import pytest

from core.payments.contracts import PAYMENT_SCHEMA_VERSION, PaymentLifecycleStatus
from core.payments.read_model import (
    PaymentHistoryInvariantViolation,
    PaymentNotFound,
    PaymentProjector,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _metadata(*, business_id: str = "business", product_id: str = "product", order_id: str = "order") -> dict[str, str]:
    return {
        "tenant_id": "tenant",
        "business_id": business_id,
        "product_id": product_id,
        "order_id": order_id,
    }


def _event(
    event_type: str,
    ts: int,
    *,
    external_id: str = "payment-123456",
    source: str = "payments",
    schema_version: int | None = PAYMENT_SCHEMA_VERSION,
    metadata: dict[str, str] | None = None,
    **extra,
) -> dict:
    payload = {
        "external_id": external_id,
        "metadata": dict(metadata or _metadata()),
        **extra,
    }
    if schema_version is not None:
        payload["schema_version"] = schema_version
    return {
        "tenant_id": "tenant",
        "event_type": event_type,
        "source": source,
        "timestamp_ms": ts,
        "payload": payload,
    }


def _created(ts: int = 10, **kwargs) -> dict:
    return _event(
        "payment_created",
        ts,
        provider="yookassa",
        amount=12550,
        currency="eur",
        status="pending",
        **kwargs,
    )


def test_payment_projector_replays_v2_success_to_terminal_capture() -> None:
    events = MemoryEventStore([
        _created(),
        _event("payment_checked", 20, status="pending"),
        _event("payment_succeeded", 30, status="succeeded"),
        _event("payment_captured", 40, status="succeeded"),
    ])
    payment = PaymentProjector(events).get(
        tenant_id="tenant", business_id="business", external_id="payment-123456"
    )
    assert payment.identity.tenant_id == "tenant"
    assert payment.identity.business_id == "business"
    assert payment.identity.product_id == "product"
    assert payment.identity.order_id == "order"
    assert payment.identity.provider == "yookassa"
    assert payment.amount_minor == 12550
    assert payment.currency == "EUR"
    assert payment.lifecycle_status is PaymentLifecycleStatus.SUCCEEDED
    assert payment.terminal_at_ms == 40
    assert payment.captured_at_ms == 40


def test_payment_projector_allows_recovery_check_after_succeeded_before_capture() -> None:
    events = MemoryEventStore([
        _created(),
        _event("payment_succeeded", 20, status="succeeded"),
        _event("payment_checked", 30, status="succeeded"),
        _event("payment_captured", 40, status="succeeded"),
    ])
    payment = PaymentProjector(events).get(
        tenant_id="tenant", business_id="business", external_id="payment-123456"
    )
    assert payment.lifecycle_status is PaymentLifecycleStatus.SUCCEEDED
    assert payment.captured_at_ms == 40


def test_payment_projector_replays_failed_as_terminal() -> None:
    events = MemoryEventStore([
        _created(),
        _event("payment_checked", 20, status="failed"),
        _event("payment_failed", 30, status="failed"),
    ])
    payment = PaymentProjector(events).get(
        tenant_id="tenant", business_id="business", external_id="payment-123456"
    )
    assert payment.lifecycle_status is PaymentLifecycleStatus.FAILED
    assert payment.terminal_at_ms == 30
    assert payment.captured_at_ms is None


def test_payment_projector_ignores_legacy_pre_v2_history() -> None:
    events = MemoryEventStore([
        _created(schema_version=None),
        _event("payment_captured", 20, schema_version=None, status="succeeded"),
    ])
    with pytest.raises(PaymentNotFound):
        PaymentProjector(events).get(
            tenant_id="tenant", business_id="business", external_id="payment-123456"
        )


def test_payment_projector_fails_closed_on_unknown_schema_or_source() -> None:
    with pytest.raises(PaymentHistoryInvariantViolation, match="schema"):
        PaymentProjector(MemoryEventStore([_created(schema_version=999)])).get(
            tenant_id="tenant", business_id="business", external_id="payment-123456"
        )
    with pytest.raises(PaymentHistoryInvariantViolation, match="non-canonical source"):
        PaymentProjector(MemoryEventStore([_created(source="foreign")])).get(
            tenant_id="tenant", business_id="business", external_id="payment-123456"
        )


def test_payment_projector_fails_closed_on_scope_change_and_post_terminal_history() -> None:
    events = MemoryEventStore([
        _created(),
        _event("payment_checked", 20),
    ])
    events[-1]["payload"]["metadata"]["product_id"] = "other"
    with pytest.raises(PaymentHistoryInvariantViolation, match="immutable scope"):
        PaymentProjector(events).get(
            tenant_id="tenant", business_id="business", external_id="payment-123456"
        )

    post_terminal = MemoryEventStore([
        _created(),
        _event("payment_failed", 20, status="failed"),
        _event("payment_checked", 30, status="failed"),
    ])
    with pytest.raises(PaymentHistoryInvariantViolation, match="continues after terminal"):
        PaymentProjector(post_terminal).get(
            tenant_id="tenant", business_id="business", external_id="payment-123456"
        )


def test_payment_projector_lists_only_requested_business() -> None:
    events = MemoryEventStore([
        _created(external_id="payment-111111"),
        _created(external_id="payment-222222", metadata=_metadata(business_id="other")),
    ])
    rows = PaymentProjector(events).list_for_business(tenant_id="tenant", business_id="business")
    assert [row.identity.external_id for row in rows] == ["payment-111111"]


def test_payment_projector_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "payments.sqlite3"
    with SqliteEventStore(str(path)) as events:
        for row in (
            _created(),
            _event("payment_succeeded", 20, status="succeeded"),
            _event("payment_captured", 30, status="succeeded"),
        ):
            events.append_event(row)
    with SqliteEventStore(str(path)) as events:
        payment = PaymentProjector(events).get(
            tenant_id="tenant", business_id="business", external_id="payment-123456"
        )
    assert payment.lifecycle_status is PaymentLifecycleStatus.SUCCEEDED
    assert payment.captured_at_ms == 30
