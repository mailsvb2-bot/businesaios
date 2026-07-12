from __future__ import annotations

from types import SimpleNamespace

from runtime._internal.effects_actions.payments.reconciliation import (
    _emit_payment_captured,
    _terminal_event_id,
)
from runtime._internal.effects_actions.payments.reconciliation_support import (
    TERMINAL_EVENTS,
    event_already_processed,
    resolve_created_payment_context,
)


class FakeEventLog:
    def __init__(self, events=None) -> None:
        self.events = list(events or [])

    def iter_events(self):
        return iter(self.events)

    def emit(self, **event):
        self.events.append(dict(event))


class FakePaymentOutbox:
    def __init__(self, terminal_status: str | None = None) -> None:
        self.status = terminal_status
        self.calls: list[dict] = []

    def terminal_status(self, external_id: str) -> str | None:
        return self.status

    def try_mark_terminal_emitted(self, **kwargs) -> bool:
        self.calls.append(dict(kwargs))
        if self.status is not None:
            return False
        self.status = str(kwargs["terminal_status"])
        return True


def _effects(events, *, payment_outbox=None) -> SimpleNamespace:
    return SimpleNamespace(
        event_log=FakeEventLog(events),
        payment_outbox=payment_outbox,
    )


def _captured_kwargs() -> dict:
    return {
        "original_decision_id": "decision-create-8",
        "original_correlation_id": "correlation-create-8",
        "reconciliation_decision_id": "decision-reconcile-8",
        "reconciliation_correlation_id": "correlation-reconcile-8",
        "user_id": "user-8",
        "external_id": "payment-8",
        "status": "succeeded",
        "business_metadata": {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "order_id": "order-8",
        },
    }


def test_payment_checked_is_not_terminal_and_can_be_reconciled_again() -> None:
    effects = _effects(
        [
            {
                "event_type": "payment_checked",
                "payload": {"external_id": "payment-1", "status": "pending"},
            }
        ]
    )

    assert "payment_checked" not in TERMINAL_EVENTS
    assert event_already_processed(effects=effects, external_id="payment-1") is False


def test_terminal_marker_without_proof_does_not_block_reconciliation() -> None:
    outbox = FakePaymentOutbox(terminal_status="succeeded")
    effects = _effects([], payment_outbox=outbox)

    assert event_already_processed(effects=effects, external_id="payment-marker-only") is False


def test_payment_captured_is_terminal_proof_and_repairs_missing_marker() -> None:
    outbox = FakePaymentOutbox()
    effects = _effects(
        [
            {
                "event_type": "payment_captured",
                "payload": {"external_id": "payment-2", "status": "succeeded"},
            }
        ],
        payment_outbox=outbox,
    )

    assert event_already_processed(effects=effects, external_id="payment-2") is True
    assert outbox.status == "succeeded"
    assert outbox.calls[-1]["event"] == "payment_captured"


def test_payment_failed_is_terminal_proof_and_repairs_missing_marker() -> None:
    outbox = FakePaymentOutbox()
    effects = _effects(
        [
            {
                "event_type": "payment_failed",
                "payload": {"external_id": "payment-failed", "status": "failed"},
            }
        ],
        payment_outbox=outbox,
    )

    assert event_already_processed(effects=effects, external_id="payment-failed") is True
    assert outbox.status == "failed"


def test_created_payment_context_preserves_business_product_order_causality() -> None:
    effects = _effects(
        [
            {
                "event_type": "payment_created",
                "decision_id": "decision-create-7",
                "correlation_id": "correlation-create-7",
                "user_id": "user-7",
                "payload": {
                    "external_id": "payment-7",
                    "metadata": {
                        "tenant_id": "business-a",
                        "product_id": "crm-pro",
                        "order_id": "order-7",
                        "ignored_provider_field": "not-causal",
                    },
                },
            }
        ]
    )

    context = resolve_created_payment_context(effects=effects, external_id="payment-7")

    assert context == {
        "envelope_id": "decision-create-7",
        "user_id": "user-7",
        "correlation_id": "correlation-create-7",
        "metadata": {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "order_id": "order-7",
        },
    }


def test_payment_terminal_event_id_is_deterministic_per_original_decision_and_payment() -> None:
    first = _terminal_event_id(
        event_type="payment_captured",
        external_id="payment-8",
        original_decision_id="decision-create-8",
    )
    second = _terminal_event_id(
        event_type="payment_captured",
        external_id="payment-8",
        original_decision_id="decision-create-8",
    )
    different = _terminal_event_id(
        event_type="payment_failed",
        external_id="payment-8",
        original_decision_id="decision-create-8",
    )

    assert first == second
    assert first != different


def test_payment_captured_is_attributed_to_original_payment_decision_and_scope() -> None:
    effects = _effects([])

    event_id = _emit_payment_captured(effects, **_captured_kwargs())

    event = effects.event_log.events[-1]
    assert event["event_type"] == "payment_captured"
    assert event["event_id"] == event_id
    assert event["decision_id"] == "decision-create-8"
    assert event["correlation_id"] == "correlation-create-8"
    assert event["payload"]["reconciled_by_decision_id"] == "decision-reconcile-8"
    assert event["payload"]["metadata"] == {
        "tenant_id": "business-a",
        "product_id": "crm-pro",
        "order_id": "order-8",
    }


def test_repeated_payment_captured_emit_keeps_one_deterministic_proof_event() -> None:
    effects = _effects([])

    first = _emit_payment_captured(effects, **_captured_kwargs())
    second = _emit_payment_captured(effects, **_captured_kwargs())

    assert first == second
    captured = [event for event in effects.event_log.events if event.get("event_type") == "payment_captured"]
    assert len(captured) == 1
    assert captured[0]["event_id"] == first
