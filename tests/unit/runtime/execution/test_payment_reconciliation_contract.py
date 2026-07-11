from __future__ import annotations

from types import SimpleNamespace

from runtime._internal.effects_actions.payments.reconciliation import _emit_payment_captured
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


def _effects(events) -> SimpleNamespace:
    return SimpleNamespace(
        event_log=FakeEventLog(events),
        payment_outbox=None,
    )


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


def test_payment_captured_is_terminal_proof() -> None:
    effects = _effects(
        [
            {
                "event_type": "payment_captured",
                "payload": {"external_id": "payment-2", "status": "succeeded"},
            }
        ]
    )

    assert event_already_processed(effects=effects, external_id="payment-2") is True


def test_created_payment_context_matches_dict_contract_used_by_reconciler() -> None:
    effects = _effects(
        [
            {
                "event_type": "payment_created",
                "decision_id": "decision-create-7",
                "correlation_id": "correlation-create-7",
                "user_id": "user-7",
                "payload": {"external_id": "payment-7"},
            }
        ]
    )

    context = resolve_created_payment_context(effects=effects, external_id="payment-7")

    assert context == {
        "envelope_id": "decision-create-7",
        "user_id": "user-7",
        "correlation_id": "correlation-create-7",
    }


def test_payment_captured_is_attributed_to_original_payment_decision() -> None:
    effects = _effects([])

    _emit_payment_captured(
        effects,
        original_decision_id="decision-create-8",
        original_correlation_id="correlation-create-8",
        reconciliation_decision_id="decision-reconcile-8",
        reconciliation_correlation_id="correlation-reconcile-8",
        user_id="user-8",
        external_id="payment-8",
        status="succeeded",
    )

    event = effects.event_log.events[-1]
    assert event["event_type"] == "payment_captured"
    assert event["decision_id"] == "decision-create-8"
    assert event["correlation_id"] == "correlation-create-8"
    assert event["payload"]["reconciled_by_decision_id"] == "decision-reconcile-8"
