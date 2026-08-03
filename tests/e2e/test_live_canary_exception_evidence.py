from __future__ import annotations

from types import SimpleNamespace

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from core.events.event_types import KNOWN_EVENT_TYPES
from core.experiments.live_canary_events import (
    LIVE_CANARY_EXECUTION_FAILED_SOURCE,
)
from runtime.execution import executor_trace_runtime
from runtime.experiments.hooks import record_live_canary_executor_exception
from runtime.experiments.live_canary import LiveCanaryCoordinator


class MemoryEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(self, **kwargs):
        row = dict(kwargs)
        self.rows.append(row)
        return row

    def get_events(self, decision_id, event_type):
        return [
            row
            for row in self.rows
            if row.get("decision_id") == decision_id
            and row.get("event_type") == event_type
        ]

    def iter_events(self):
        return iter(self.rows)


class Registry:
    def __init__(self) -> None:
        self.candidate_policy_id = "candidate@v2"
        self.rollout_pct = 100
        self.calls: list[dict] = []

    def rollout_config(self):
        return self.candidate_policy_id, self.rollout_pct

    def snapshot_runtime_state(self):
        return self.rollout_pct, tuple(self.calls)

    def restore_runtime_state(self, snapshot):
        self.rollout_pct, calls = snapshot
        self.calls = list(calls)

    def set_rollout(self, **kwargs):
        self.candidate_policy_id = str(kwargs["candidate_policy_id"])
        self.rollout_pct = int(kwargs["rollout_pct"])
        self.calls.append(dict(kwargs))


def policy() -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="exception-evidence",
        candidate_policy_id="candidate@v2",
        assignment_secret="e" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_purposes=("live_canary",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        max_candidate_actions_per_day=100,
        max_candidate_actions_per_subject_24h=100,
        max_daily_cost=1000.0,
        min_assignments=100,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=60,
        outcome_window_seconds=60,
    )


def assigned_runtime():
    events = MemoryEvents()
    registry = Registry()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=policy(),
    )
    coordinator.assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        decision_id="exception-d-1",
        correlation_id="exception-c-1",
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
        expected_cost=1.0,
    )
    executor = SimpleNamespace(
        _decision_core=SimpleNamespace(_live_canary=coordinator)
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="exception-d-1",
            correlation_id="exception-c-1",
            action="send_message@v1",
            payload={"expected_cost": 1.0},
        )
    )
    return events, registry, executor, env


def test_execution_failure_source_is_in_strict_event_vocabulary() -> None:
    assert LIVE_CANARY_EXECUTION_FAILED_SOURCE in KNOWN_EVENT_TYPES


def test_executor_exception_records_fail_closed_canary_evidence() -> None:
    events, registry, executor, env = assigned_runtime()

    record_live_canary_executor_exception(
        executor=executor,
        env=env,
        exc=RuntimeError("provider bookkeeping failed"),
    )

    source = events.get_events(
        "exception-d-1",
        LIVE_CANARY_EXECUTION_FAILED_SOURCE,
    )
    assert len(source) == 1
    assert source[0]["payload"]["ok"] is False
    executions = events.get_events(
        "exception-d-1",
        "candidate_action_executed@v1",
    )
    assert len(executions) == 1
    assert executions[0]["payload"]["ok"] is False
    assert registry.rollout_pct == 0


def test_runtime_exception_path_records_canary_evidence_and_reraises(
    monkeypatch,
) -> None:
    called = {}
    original = RuntimeError("provider dispatch exploded")

    def raise_original(**_kwargs):
        raise original

    monkeypatch.setattr(
        executor_trace_runtime,
        "build_executor_entrypoint_bundle",
        lambda **_kwargs: SimpleNamespace(run=raise_original),
    )
    monkeypatch.setattr(
        executor_trace_runtime,
        "record_live_canary_executor_exception",
        lambda **kwargs: called.update(kwargs),
    )
    executor = SimpleNamespace(
        _events=MemoryEvents(),
        _snapshot_store=object(),
        _runtime_observability=None,
        _trace_context_for_env=lambda _env: None,
        _append_decision_trace=lambda *_args: None,
        _record_action_audit=lambda **_kwargs: None,
        _record_connector_runtime_event=lambda **_kwargs: None,
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="exception-d-2",
            correlation_id="exception-c-2",
            action="send_message@v1",
            payload={"tenant_id": "tenant-a"},
        )
    )

    with pytest.raises(RuntimeError) as caught:
        executor_trace_runtime.execute_with_trace(executor=executor, env=env)

    assert caught.value is original
    assert called == {"executor": executor, "env": env, "exc": original}
