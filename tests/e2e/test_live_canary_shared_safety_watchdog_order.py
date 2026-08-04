from __future__ import annotations

from types import SimpleNamespace

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.guardrails import CanaryDecision, GuardrailResult
from core.security.call_origin import assert_called_from_runtime_executor
from runtime.execution import executor_trace_runtime
from runtime.executor import RuntimeExecutor
from runtime.experiments import wiring
from runtime.experiments.live_canary import LiveCanaryCoordinator


class SharedEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self._clock = 1_000

    def emit(self, **kwargs):
        self._clock += 1
        row = {
            "tenant_id": self.tenant_id,
            "timestamp_ms": self._clock,
            **kwargs,
        }
        self.rows.append(row)
        return row

    def iter_events(
        self,
        *,
        start_ms=0,
        end_ms=None,
        event_types=None,
        **_kwargs,
    ):
        allowed = set(event_types or ())
        end = int(end_ms) if end_ms is not None else 2**63 - 1
        return iter(
            row
            for row in self.rows
            if int(row["timestamp_ms"]) >= int(start_ms)
            and int(row["timestamp_ms"]) < end
            and (not allowed or row["event_type"] in allowed)
        )

    def get_events(self, decision_id, event_type):
        return [
            row
            for row in self.rows
            if row.get("decision_id") == decision_id
            and row.get("event_type") == event_type
        ]


class SharedRegistry:
    def rollout_config(self):
        return "candidate@v2", 100

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")


def policy(*, daily_limit: int = 1) -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="shared-safety",
        candidate_policy_id="candidate@v2",
        assignment_secret="s" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_purposes=("live_canary",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        max_candidate_actions_per_day=daily_limit,
        max_candidate_actions_per_subject_24h=100,
        max_daily_cost=10_000.0,
        min_assignments=1_000,
        min_candidate_assignments=100,
        min_outcomes_per_arm=100,
        min_duration_seconds=60,
        outcome_window_seconds=60,
        outcome_poll_seconds=1.0,
    )


def coordinator(events, registry) -> LiveCanaryCoordinator:
    return LiveCanaryCoordinator(
        event_log=events,
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=policy(),
    )


def test_shared_safety_refresh_blocks_second_coordinator_assignment() -> None:
    events = SharedEvents()
    registry = SharedRegistry()
    first = coordinator(events, registry)
    second = coordinator(events, registry)
    first._assignment_safety.ensure_loaded()
    second._assignment_safety.ensure_loaded()

    first.assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        decision_id="decision-1",
        correlation_id="correlation-1",
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
    )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_ASSIGNMENT_GUARD_BLOCKED",
    ):
        second.assign(
            tenant_id="tenant-a",
            subject_id="customer-2",
            decision_id="decision-2",
            correlation_id="correlation-2",
            production_policy_id="active@v1",
            action="send_message@v1",
            purpose="live_canary",
            eligible=True,
        )

    metrics = second._assignment_safety.metrics(candidate_pct=100.0)
    assert metrics["candidate_actions_24h"] == 2
    assert second.rollback_required is True


def test_runtime_executor_gateway_satisfies_sovereign_call_origin() -> None:
    rollback = GuardrailResult(
        CanaryDecision.ROLLBACK,
        ("candidate_error_rate",),
        {},
    )

    class Coordinator:
        candidate_policy_id = "candidate@v2"
        policy = SimpleNamespace(experiment_id="watchdog-runtime")

        def evaluate_and_maybe_rollback(self, **_kwargs):
            assert_called_from_runtime_executor()
            return rollback

    executor = RuntimeExecutor.__new__(RuntimeExecutor)
    executor._decision_core = SimpleNamespace(_live_canary=Coordinator())

    result = executor.submit_live_canary_rollback(
        decision_id="watchdog-1",
        correlation_id="watchdog-c-1",
        tenant_id="tenant-a",
        candidate_policy_id="candidate@v2",
        experiment_id="watchdog-runtime",
        reasons=("candidate_error_rate",),
    )

    assert result is rollback


def test_wiring_submits_watchdog_rollback_through_runtime_executor(
    monkeypatch,
) -> None:
    rollback = GuardrailResult(
        CanaryDecision.ROLLBACK,
        ("candidate_error_rate",),
        {},
    )
    calls: list[str] = []

    class Coordinator:
        candidate_policy_id = "candidate@v2"
        policy = SimpleNamespace(
            experiment_id="watchdog-runtime",
            allowed_tenant_ids=("tenant-a",),
            outcome_poll_seconds=1.0,
        )

        def _guard_result(self):
            return rollback

        def _open_local_circuit(self, *_args, **_kwargs):
            calls.append("circuit")

    supervisors = []

    class Supervisor:
        def __init__(self, watchdog):
            self.watchdog = watchdog
            supervisors.append(self)

        def start(self):
            calls.append("start")

    monkeypatch.setattr(wiring, "LiveCanaryWatchdogSupervisor", Supervisor)
    core = SimpleNamespace(_live_canary=Coordinator())

    class Executor:
        _decision_core = core

        def submit_live_canary_rollback(self, **_kwargs):
            calls.append("executor-rollback")
            return rollback

    executor = Executor()
    wiring.bind_live_canary_executor(core, executor)
    supervisors[0].watchdog.run_once()

    assert calls == ["start", "circuit", "executor-rollback"]
    assert executor._live_canary_watchdog is supervisors[0].watchdog


def test_success_evidence_waits_for_fallible_bookkeeping(monkeypatch) -> None:
    result = SimpleNamespace(ok=True, output={}, error=None)
    calls: list[str] = []

    monkeypatch.setattr(
        executor_trace_runtime,
        "build_executor_entrypoint_bundle",
        lambda **_kwargs: SimpleNamespace(
            run=lambda **_kwargs: result,
        ),
    )
    monkeypatch.setattr(
        executor_trace_runtime,
        "record_live_canary_executor_result",
        lambda **_kwargs: calls.append("success"),
    )
    monkeypatch.setattr(
        executor_trace_runtime,
        "record_live_canary_executor_exception",
        lambda **_kwargs: calls.append("failure"),
    )

    def audit(*, status, **_kwargs):
        if status == "succeeded":
            raise RuntimeError("audit persistence failed")

    executor = SimpleNamespace(
        _events=SharedEvents(),
        _snapshot_store=object(),
        _runtime_observability=None,
        _trace_context_for_env=lambda _env: None,
        _append_decision_trace=lambda *_args: None,
        _record_action_audit=audit,
        _record_connector_runtime_event=lambda **_kwargs: None,
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="bookkeeping-d-1",
            correlation_id="bookkeeping-c-1",
            action="send_message@v1",
            payload={"tenant_id": "tenant-a"},
        )
    )

    with pytest.raises(RuntimeError, match="audit persistence failed"):
        executor_trace_runtime.execute_with_trace(executor=executor, env=env)

    assert calls == ["failure"]
