from __future__ import annotations

import time
from types import SimpleNamespace

from config.live_canary_policy import LiveCanaryPolicy
from runtime._internal.effects_actions.payments.reconciliation import (
    _emit_payment_status_event,
)
from runtime.experiments.live_canary import LiveCanaryCoordinator
from runtime.experiments.outcome_observer import LiveCanaryOutcomeObserver


class MemoryEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(
        self,
        *,
        event_type,
        source,
        user_id,
        payload,
        decision_id=None,
        correlation_id=None,
        event_id=None,
        **_kwargs,
    ):
        row = {
            "event_id": event_id,
            "event_type": event_type,
            "source": source,
            "user_id": user_id,
            "payload": dict(payload),
            "decision_id": decision_id,
            "correlation_id": correlation_id,
        }
        self.rows.append(row)
        return row

    def get_events(self, decision_id, event_type):
        return [
            row
            for row in self.rows
            if row["decision_id"] == decision_id
            and row["event_type"] == event_type
        ]

    def iter_events(self):
        return iter(self.rows)


class Registry:
    def __init__(self) -> None:
        self.rollout_pct = 100

    def rollout_config(self):
        return "candidate@v2", self.rollout_pct

    def snapshot_runtime_state(self):
        return self.rollout_pct

    def restore_runtime_state(self, snapshot):
        self.rollout_pct = snapshot

    def set_rollout(self, **kwargs):
        self.rollout_pct = int(kwargs["rollout_pct"])


def policy_for(*outcome_event_types: str) -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="observer-canary",
        assignment_secret="o" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=tuple(outcome_event_types),
        max_candidate_actions_per_day=10,
        max_candidate_actions_per_subject_24h=1,
        max_daily_cost=100.0,
        min_assignments=100,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=60,
        outcome_window_seconds=60,
    )


def assigned_coordinator(
    events: MemoryEvents,
    *,
    decision_id: str,
    outcome_event_types: tuple[str, ...],
) -> LiveCanaryCoordinator:
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=Registry(),
        candidate_policy_id="candidate@v2",
        policy=policy_for(*outcome_event_types),
    )
    coordinator.assign(
        tenant_id="tenant-a",
        subject_id=f"customer-{decision_id}",
        decision_id=decision_id,
        correlation_id=f"correlation-{decision_id}",
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
    )
    return coordinator


def observed_outcomes(events: MemoryEvents, decision_id: str) -> list[dict]:
    return events.get_events(decision_id, "business_outcome_observed@v1")


def test_observer_attributes_real_webhook_once() -> None:
    events = MemoryEvents()
    coordinator = assigned_coordinator(
        events,
        decision_id="d-1",
        outcome_event_types=("booking_confirmed@v1",),
    )
    events.emit(
        event_type="booking_confirmed@v1",
        source="booking_webhook",
        user_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={
            "success": True,
            "amount": 3500.0,
            "observed_at_ms": int(time.time() * 1000),
        },
    )

    observer = LiveCanaryOutcomeObserver(coordinator)

    assert observer.poll_once() == 1
    assert observer.poll_once() == 0
    outcomes = observed_outcomes(events, "d-1")
    assert len(outcomes) == 1
    assert outcomes[0]["payload"]["revenue"] == 3500.0


def test_observer_infers_purchase_success_without_boolean_flag() -> None:
    events = MemoryEvents()
    coordinator = assigned_coordinator(
        events,
        decision_id="purchase-1",
        outcome_event_types=("purchase_success",),
    )
    events.emit(
        event_type="purchase_success",
        source="product_telemetry",
        user_id="customer-purchase",
        decision_id="purchase-1",
        correlation_id="correlation-purchase-1",
        payload={
            "offer_id": "offer-1",
            "receipt_id": "receipt-1",
            "amount": 199.0,
            "observed_at_ms": int(time.time() * 1000),
        },
    )

    assert LiveCanaryOutcomeObserver(coordinator).poll_once() == 1
    outcome = observed_outcomes(events, "purchase-1")[0]["payload"]
    assert outcome["success"] is True
    assert outcome["revenue"] == 199.0


def test_observer_infers_payment_success_from_canonical_status() -> None:
    events = MemoryEvents()
    coordinator = assigned_coordinator(
        events,
        decision_id="payment-1",
        outcome_event_types=("payment_succeeded",),
    )
    events.emit(
        event_type="payment_succeeded",
        source="payments",
        user_id="customer-payment",
        decision_id="payment-1",
        correlation_id="correlation-payment-1",
        payload={
            "external_id": "payment-ext-1",
            "status": "succeeded",
            "amount": 499.0,
            "observed_at_ms": int(time.time() * 1000),
        },
    )

    assert LiveCanaryOutcomeObserver(coordinator).poll_once() == 1
    outcome = observed_outcomes(events, "payment-1")[0]["payload"]
    assert outcome["success"] is True
    assert outcome["revenue"] == 499.0


def test_payment_terminal_event_uses_originating_decision() -> None:
    events = MemoryEvents()
    effects = SimpleNamespace(event_log=events)

    _emit_payment_status_event(
        effects,
        event_type="payment_succeeded",
        original_decision_id="payment-origin-1",
        reconciliation_decision_id="payment-reconcile-1",
        reconciliation_correlation_id="reconcile-correlation-1",
        user_id="customer-payment",
        external_id="payment-ext-1",
        status="succeeded",
        business_metadata={"tenant_id": "tenant-a", "order_id": "order-1"},
    )

    emitted = events.rows[0]
    assert emitted["decision_id"] == "payment-origin-1"
    assert emitted["payload"]["original_decision_id"] == "payment-origin-1"
    assert (
        emitted["payload"]["reconciled_by_decision_id"]
        == "payment-reconcile-1"
    )
