from __future__ import annotations

import time
from types import SimpleNamespace

from config.live_canary_policy import LiveCanaryPolicy
from core.policies.selector import PolicySelector
from runtime.experiments.outcome_observer import LiveCanaryOutcomeObserver


class SelectorRegistry:
    def __init__(self) -> None:
        self.active_policy = SimpleNamespace(id="active@v1")
        self.candidate_policy = SimpleNamespace(id="candidate@v2")
        self.demand_policy = SimpleNamespace(id="demand_route@v1")

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")

    def canary_ref(self):
        return SimpleNamespace(policy_id="candidate@v2")

    def active(self):
        return self.active_policy

    def get(self, policy_id):
        return {
            "active@v1": self.active_policy,
            "candidate@v2": self.candidate_policy,
            "demand_route@v1": self.demand_policy,
        }[str(policy_id)]

    def rollout_config(self):
        return "candidate@v2", 100


def routing_policy(*, purposes=("live_canary",)) -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="routing-parity",
        candidate_policy_id="candidate@v2",
        assignment_secret="r" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_purposes=purposes,
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        min_assignments=10,
        min_candidate_assignments=1,
        min_outcomes_per_arm=1,
        min_duration_seconds=1,
        outcome_window_seconds=60,
    )


def test_selector_hashes_the_same_nested_actor_as_assignment_boundary() -> None:
    selector = PolicySelector(SelectorRegistry())
    selector._resolver.live_policy = routing_policy()
    captured = {}

    def select_policy(user_id, **kwargs):
        captured["user_id"] = user_id
        captured.update(kwargs)
        return SimpleNamespace(policy_id="candidate@v2")

    selector._resolver.select_policy = select_policy
    state = {
        "product_metadata": {"tenant_id": "tenant-a"},
        "user": {"actor_id": "canonical-actor"},
        "meta": {
            "user_id": "metadata-target-user",
            "purpose": "live_canary",
            "live_canary_eligible": True,
        },
    }

    assert selector.resolve_policy(state).id == "candidate@v2"
    assert captured["user_id"] == "canonical-actor"
    assert captured["tenant_id"] == "tenant-a"


def test_foreign_tenant_keeps_its_canonical_purpose_policy() -> None:
    selector = PolicySelector(SelectorRegistry())
    selector._resolver.live_policy = routing_policy(purposes=("demand_route",))
    state = {
        "tenant_id": "tenant-foreign",
        "user_id": "customer-1",
        "purpose": "demand_route",
        "live_canary_eligible": True,
    }

    assert selector.resolve_policy(state).id == "demand_route@v1"


class CursorEvents:
    tenant_id = "tenant-a"

    def __init__(self, rows):
        self.rows = list(rows)
        self.after_append_seq_calls: list[int] = []
        self.start_ms_calls: list[int] = []

    def latest_append_seq(self, *, tenant_id: str) -> int:
        assert tenant_id == self.tenant_id
        return len(self.rows)

    def iter_events(
        self,
        *,
        start_ms=0,
        end_ms=None,
        after_append_seq=0,
        event_types=None,
        **_kwargs,
    ):
        self.start_ms_calls.append(int(start_ms))
        self.after_append_seq_calls.append(int(after_append_seq or 0))
        allowed = set(event_types or ())
        end = int(end_ms) if end_ms is not None else 2**63 - 1
        return iter(
            {**row, "append_seq": append_seq}
            for append_seq, row in enumerate(self.rows, start=1)
            if append_seq > int(after_append_seq or 0)
            and int(row["timestamp_ms"]) >= int(start_ms)
            and int(row["timestamp_ms"]) < end
            and (not allowed or row["event_type"] in allowed)
        )


class CursorLedger:
    def assignment_for_decision(self, decision_id):
        return {
            "eligible": True,
            "arm": "candidate",
            "tenant_id": "tenant-a",
        }

    def events_for_decision(self, decision_id, event_type):
        return []


class CursorCoordinator:
    def __init__(self, event_log):
        self.event_log = event_log
        self.policy = SimpleNamespace(
            outcome_window_seconds=60,
            outcome_event_types=("booking_confirmed@v1",),
        )
        self.ledger = CursorLedger()
        self.recorded: list[dict] = []

    def record_outcome(self, **kwargs):
        self.recorded.append(dict(kwargs))
        return kwargs


def source_event(
    decision_id: str,
    timestamp_ms: int,
    event_id: str,
    *,
    observed_at_ms: int | None = None,
):
    payload = {"success": True, "amount": 3500.0}
    if observed_at_ms is not None:
        payload["observed_at_ms"] = observed_at_ms
    return {
        "event_id": event_id,
        "tenant_id": "tenant-a",
        "event_type": "booking_confirmed@v1",
        "source": "booking_webhook",
        "user_id": "customer-1",
        "decision_id": decision_id,
        "correlation_id": f"correlation-{decision_id}",
        "timestamp_ms": timestamp_ms,
        "payload": payload,
    }


def test_outcome_observer_advances_by_append_order() -> None:
    now_ms = int(time.time() * 1000)
    events = CursorEvents([source_event("decision-1", now_ms, "event-1")])
    coordinator = CursorCoordinator(events)
    observer = LiveCanaryOutcomeObserver(coordinator)

    assert observer.poll_once() == 1
    assert observer.poll_once() == 0
    events.rows.append(source_event("decision-2", now_ms - 1, "event-2"))
    assert observer.poll_once() == 1

    assert len(coordinator.recorded) == 2
    assert events.after_append_seq_calls == [0, 1, 1]
    assert events.start_ms_calls[0] > 0
    assert events.start_ms_calls[1:] == [0, 0]
    assert observer._append_cursor == 2
    assert observer._hydrated is True


def test_payload_time_cannot_move_the_append_cursor() -> None:
    now_ms = int(time.time() * 1000)
    future_payload_time = now_ms + 30_000
    events = CursorEvents(
        [
            source_event(
                "decision-1",
                now_ms,
                "event-1",
                observed_at_ms=future_payload_time,
            )
        ]
    )
    coordinator = CursorCoordinator(events)
    observer = LiveCanaryOutcomeObserver(coordinator)

    assert observer.poll_once() == 1
    assert observer._append_cursor == 1
    events.rows.append(source_event("decision-2", now_ms + 1, "event-2"))
    assert observer.poll_once() == 1
    assert observer._append_cursor == 2


def test_new_observer_backfills_recent_outcomes_before_following_tail() -> None:
    now_ms = int(time.time() * 1000)
    events = CursorEvents(
        [
            source_event("decision-1", now_ms - 2, "event-1"),
            source_event("decision-2", now_ms - 1, "event-2"),
        ]
    )
    coordinator = CursorCoordinator(events)
    observer = LiveCanaryOutcomeObserver(coordinator)

    assert observer.poll_once() == 2
    assert observer._append_cursor == 2
    assert observer._hydrated is True
    assert len(coordinator.recorded) == 2
