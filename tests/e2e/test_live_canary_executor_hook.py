from __future__ import annotations

from types import SimpleNamespace

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.assignment import ExperimentArm
from runtime.execution import executor_trace_runtime
from runtime.experiments.hooks import record_live_canary_executor_result
from runtime.experiments.live_canary import LiveCanaryCoordinator


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
        **_kwargs,
    ):
        row = {
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
    def __init__(self, rollout_pct: int = 100) -> None:
        self.candidate_policy_id = "candidate@v2"
        self.rollout_pct = rollout_pct
        self.calls: list[dict] = []

    def rollout_config(self):
        return self.candidate_policy_id, self.rollout_pct

    def snapshot_runtime_state(self):
        return (self.rollout_pct, tuple(self.calls))

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
        experiment_id="executor-canary",
        assignment_secret="e" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        max_candidate_actions_per_day=10,
        max_candidate_actions_per_subject_24h=1,
        max_daily_cost=100.0,
        min_assignments=100,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=60,
        outcome_window_seconds=60,
    )


def build_assignment(*, with_proof: bool):
    events = MemoryEvents()
    registry = Registry()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=policy(),
    )
    assignment = coordinator.assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
        expected_cost=1.0,
    )
    assert assignment.arm is ExperimentArm.CANDIDATE
    if with_proof:
        events.emit(
            event_type="message_sent",
            source="telegram",
            user_id="customer-1",
            decision_id="d-1",
            correlation_id="c-1",
            payload={"ok": True, "cost": 2.0},
        )
    executor = SimpleNamespace(
        _decision_core=SimpleNamespace(_live_canary=coordinator)
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="d-1",
            correlation_id="c-1",
            action="send_message@v1",
            payload={"expected_cost": 1.0},
        )
    )
    result = SimpleNamespace(ok=True, output={"cost": 1.5}, error=None)
    return events, registry, coordinator, executor, env, result


def test_executor_hook_records_real_provider_proof() -> None:
    events, registry, coordinator, executor, env, result = build_assignment(
        with_proof=True
    )
    record_live_canary_executor_result(
        executor=executor,
        env=env,
        result=result,
    )
    executions = events.get_events("d-1", "candidate_action_executed@v1")
    assert len(executions) == 1
    assert executions[0]["payload"]["cost"] == 2.0
    assert coordinator.ledger.metrics(candidate_pct=100.0)[
        "candidate_executions"
    ] == 1
    assert registry.rollout_pct == 100


def test_missing_provider_proof_rolls_back_without_raising() -> None:
    events, registry, _coordinator, executor, env, result = build_assignment(
        with_proof=False
    )
    record_live_canary_executor_result(
        executor=executor,
        env=env,
        result=result,
    )
    assert registry.rollout_pct == 0
    assert events.get_events(
        "execution-integrity:d-1",
        "canary_auto_rolled_back@v1",
    )


def test_runtime_executor_path_invokes_canary_hook(monkeypatch) -> None:
    called = {}
    result = SimpleNamespace(ok=True, output={}, error=None)
    monkeypatch.setattr(
        executor_trace_runtime,
        "build_executor_entrypoint_bundle",
        lambda **_kwargs: SimpleNamespace(run=lambda **_kwargs2: result),
    )
    monkeypatch.setattr(
        executor_trace_runtime,
        "record_live_canary_executor_result",
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
            decision_id="d-1",
            correlation_id="c-1",
            action="send_message@v1",
            payload={"tenant_id": "tenant-a"},
        )
    )
    returned = executor_trace_runtime.execute_with_trace(
        executor=executor,
        env=env,
    )
    assert returned is result
    assert called == {"executor": executor, "env": env, "result": result}
