from __future__ import annotations

import pytest

from contracts.event_store import canonical_business_event_contract
from core.payments.contracts import PAYMENT_SCHEMA_VERSION
from runtime._internal.effects_actions.payments import reconciliation


class FakeEventLog:
    def __init__(self, *, tenant_id: str, events: list[dict] | None = None) -> None:
        self.tenant_id = tenant_id
        self.events = list(events or [])

    def iter_events(self):
        return iter(self.events)

    def emit(self, **event) -> None:
        self.events.append(dict(event))


class FakeLedger:
    def __init__(self) -> None:
        self.completed: list[str] = []
        self.failed: list[str] = []

    def mark_effect_completed(self, envelope_id: str) -> None:
        self.completed.append(str(envelope_id))

    def mark_effect_failed(self, envelope_id: str) -> None:
        self.failed.append(str(envelope_id))


class FakeEffects:
    def __init__(
        self,
        *,
        tenant_id: str = "business-a",
        events: list[dict] | None = None,
        provider_status: str = "succeeded",
        ledger=True,
    ) -> None:
        self.event_log = FakeEventLog(tenant_id=tenant_id, events=events)
        self.payment_outbox = None
        self.ledger = FakeLedger() if ledger else None
        self.provider_status = provider_status
        self.provider_calls: list[str] = []

    def _yookassa_get_payment_status(self, *, external_payment_id: str) -> str:
        self.provider_calls.append(str(external_payment_id))
        return self.provider_status


def _created_payment(*, external_id: str = "payment-a", business_id: str | None = "business-a") -> dict:
    return {
        "event_id": "created-event",
        "event_type": "payment_created",
        "decision_id": "decision-create",
        "correlation_id": "correlation-create",
        "user_id": "user-a",
        "timestamp_ms": 100,
        "payload": {
            "external_id": external_id,
            "status": "pending",
            "metadata": {
                "tenant_id": "business-a",
                **({"business_id": business_id} if business_id is not None else {}),
                "product_id": "crm-pro",
                "order_id": "order-a",
            },
        },
    }


@pytest.fixture(autouse=True)
def _disable_executor_origin_guard(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(reconciliation, "assert_called_from_executor", lambda: None)


def test_foreign_or_unknown_external_payment_is_rejected_before_provider_read() -> None:
    effects = FakeEffects(events=[])

    with pytest.raises(RuntimeError, match="PAYMENT_CONTEXT_NOT_FOUND:payment-b"):
        reconciliation.reconcile_payment_effect(
            effects,
            decision_id="decision-reconcile",
            correlation_id="correlation-reconcile",
            tenant_id="business-a",
            business_id="business-a",
            external_payment_id="payment-b",
        )

    assert effects.provider_calls == []
    assert effects.event_log.events == []


def test_reconciliation_tenant_mismatch_is_rejected_before_context_or_provider_read() -> None:
    effects = FakeEffects(events=[_created_payment()])

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        reconciliation.reconcile_payment_effect(
            effects,
            decision_id="decision-reconcile",
            correlation_id="correlation-reconcile",
            tenant_id="business-b",
            business_id="business-a",
            external_payment_id="payment-a",
        )

    assert effects.provider_calls == []
    assert effects.event_log.events == [_created_payment()]


def test_locally_created_payment_reconciles_and_preserves_business_scope() -> None:
    effects = FakeEffects(events=[_created_payment()], provider_status="succeeded")

    result = reconciliation.reconcile_payment_effect(
        effects,
        decision_id="decision-reconcile",
        correlation_id="correlation-reconcile",
        tenant_id="business-a",
        business_id="business-a",
        external_payment_id="payment-a",
    )

    assert result["ok"] is True
    assert result["status"] == "succeeded"
    assert result["tenant_id"] == "business-a"
    assert result["metadata"] == {
        "tenant_id": "business-a",
        "business_id": "business-a",
        "product_id": "crm-pro",
        "order_id": "order-a",
    }
    assert effects.provider_calls == ["payment-a"]
    assert effects.ledger.completed == ["decision-create"]
    captured = [event for event in effects.event_log.events if event.get("event_type") == "payment_captured"]
    assert len(captured) == 1
    assert captured[0]["payload"]["metadata"] == result["metadata"]


def test_batch_reconciliation_requires_ledger_before_provider_work() -> None:
    effects = FakeEffects(events=[_created_payment()], ledger=False)

    with pytest.raises(RuntimeError, match="PAYMENT_LEDGER_REQUIRED"):
        reconciliation.reconcile_payments_effect(
            effects,
            decision_id="decision-batch",
            correlation_id="correlation-batch",
            tenant_id="business-a",
            business_id="business-a",
            window_min=30,
        )

    assert effects.provider_calls == []
    assert effects.event_log.events == [_created_payment()]


def test_reconciliation_business_mismatch_is_rejected_before_provider_read() -> None:
    effects = FakeEffects(events=[_created_payment()])

    with pytest.raises(RuntimeError, match="PAYMENT_BUSINESS_CONTEXT_MISMATCH"):
        reconciliation.reconcile_payment_effect(
            effects,
            decision_id="decision-reconcile",
            correlation_id="correlation-reconcile",
            tenant_id="business-a",
            business_id="business-b",
            external_payment_id="payment-a",
        )

    assert effects.provider_calls == []
    assert effects.event_log.events == [_created_payment()]


def test_legacy_unscoped_payment_is_rejected_before_provider_read() -> None:
    legacy = _created_payment(business_id=None)
    effects = FakeEffects(events=[legacy])

    with pytest.raises(RuntimeError, match="PAYMENT_BUSINESS_SCOPE_REQUIRED:payment-a"):
        reconciliation.reconcile_payment_effect(
            effects,
            decision_id="decision-reconcile",
            correlation_id="correlation-reconcile",
            tenant_id="business-a",
            business_id="business-a",
            external_payment_id="payment-a",
        )

    assert effects.provider_calls == []
    assert effects.event_log.events == [legacy]


def _canonical_native_event(event: dict) -> dict:
    return canonical_business_event_contract(
        {
            "event_id": "payment-reconciliation-proof",
            "event_type": event["event_type"],
            "source": event["source"],
            "timestamp_ms": 1,
            "decision_id": event.get("decision_id"),
            "correlation_id": event.get("correlation_id"),
            "payload": event["payload"],
        }
    )


def test_batch_reconciliation_summary_is_a_canonical_business_event() -> None:
    effects = FakeEffects(events=[])

    result = reconciliation.reconcile_payments_effect(
        effects,
        decision_id="decision-batch",
        correlation_id="correlation-batch",
        tenant_id="business-a",
        business_id="business-a",
        window_min=30,
    )

    assert result == {
        "ok": True,
        "status": "checked",
        "tenant_id": "business-a",
        "processed": 0,
    }
    summary = effects.event_log.events[-1]
    assert summary["event_type"] == "payments_reconciled"
    assert summary["payload"]["schema_version"] == PAYMENT_SCHEMA_VERSION
    assert summary["payload"]["business_id"] == "business-a"
    canonical = _canonical_native_event(summary)
    assert canonical["schema_version"] == PAYMENT_SCHEMA_VERSION
    assert canonical["business_id"] == "business-a"
    assert canonical["correlation_id"] == "correlation-batch"


def test_batch_reconciliation_failure_is_a_canonical_business_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    effects = FakeEffects(events=[])

    def fail_scan():
        raise ValueError("event scan failed")

    monkeypatch.setattr(effects.event_log, "iter_events", fail_scan)

    result = reconciliation.reconcile_payments_effect(
        effects,
        decision_id="decision-batch-failed",
        correlation_id="correlation-batch-failed",
        tenant_id="business-a",
        business_id="business-a",
        window_min=30,
    )

    assert result is False
    failed = effects.event_log.events[-1]
    assert failed["event_type"] == "payments_reconcile_failed"
    assert failed["payload"]["schema_version"] == PAYMENT_SCHEMA_VERSION
    assert failed["payload"]["tenant_id"] == "business-a"
    assert failed["payload"]["business_id"] == "business-a"
    canonical = _canonical_native_event(failed)
    assert canonical["schema_version"] == PAYMENT_SCHEMA_VERSION
    assert canonical["business_id"] == "business-a"
    assert canonical["correlation_id"] == "correlation-batch-failed"

