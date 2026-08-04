from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.decision_runtime.run import _record_live_canary_assignment
from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.assignment import ExperimentArm
from core.experiments.guardrails import CanaryDecision
from core.policies.canary import CanaryPolicyResolver
from runtime._internal.effects_actions import policy_actions
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


class BrokenEvents(MemoryEvents):
    def iter_events(self):
        raise OSError("ledger unavailable")


class Registry:
    def __init__(self, *, rollout_pct: int = 0) -> None:
        self.calls: list[dict] = []
        self.candidate_policy_id = "candidate@v2"
        self.rollout_pct = rollout_pct

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")

    def snapshot_runtime_state(self):
        return (tuple(self.calls), self.rollout_pct)

    def restore_runtime_state(self, snapshot):
        calls, self.rollout_pct = snapshot
        self.calls = list(calls)

    def set_rollout(self, **kwargs):
        self.calls.append(dict(kwargs))
        self.candidate_policy_id = str(kwargs["candidate_policy_id"])
        self.rollout_pct = int(kwargs["rollout_pct"])

    def rollout_config(self):
        return self.candidate_policy_id, self.rollout_pct


def live_policy(*, candidate_pct: float = 1.0) -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="metro-followup-2026-08",
        assignment_secret="x" * 32,
        candidate_pct=candidate_pct,
        max_candidate_pct=100.0,
        initial_canary_pct=1,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        min_assignments=1000,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=86_400,
        outcome_window_seconds=86_400,
    )


def test_unavailable_evidence_ledger_forces_rollback() -> None:
    registry = Registry(rollout_pct=1)
    coordinator = LiveCanaryCoordinator(
        event_log=BrokenEvents(),
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=live_policy(),
    )
    result = coordinator.evaluate_and_maybe_rollback(
        decision_id="watchdog-1",
        correlation_id="canary-1",
        tenant_id="tenant-a",
    )
    assert result.decision is CanaryDecision.ROLLBACK
    assert result.reasons == ("evaluation_error:OSError",)
    assert registry.calls[-1]["rollout_pct"] == 0


def test_secret_bucket_is_stable_and_tenant_allowlisted() -> None:
    active = SimpleNamespace(policy_id="active@v1")
    candidate = SimpleNamespace(policy_id="candidate@v2")
    registry = SimpleNamespace(active=lambda: active, canary=lambda: candidate)
    resolver = CanaryPolicyResolver(
        registry,
        SimpleNamespace(canary_pct=0.5),
        live_policy(candidate_pct=50.0),
    )
    kwargs = {"purpose": "live_canary", "eligible": True}
    first = resolver.resolve_policy(
        "customer-1",
        tenant_id="tenant-a",
        **kwargs,
    )
    second = resolver.resolve_policy(
        "customer-1",
        tenant_id="tenant-a",
        **kwargs,
    )
    foreign = resolver.resolve_policy(
        "customer-1",
        tenant_id="tenant-b",
        **kwargs,
    )
    ineligible = resolver.resolve_policy(
        "customer-1",
        tenant_id="tenant-a",
        purpose="live_canary",
        eligible=False,
    )
    assert first.policy_id == second.policy_id
    assert foreign.policy_id == active.policy_id
    assert ineligible.policy_id == active.policy_id


def test_decision_runtime_records_selected_arm_and_blocks_mismatch() -> None:
    events = MemoryEvents()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=Registry(rollout_pct=100),
        candidate_policy_id="candidate@v2",
        policy=live_policy(candidate_pct=100.0),
    )
    core = SimpleNamespace(
        _live_canary=coordinator,
        _selector=SimpleNamespace(
            _registry=SimpleNamespace(
                active_ref=lambda: SimpleNamespace(policy_id="active@v1")
            )
        ),
    )
    state = {
        "meta": {
            "purpose": "live_canary",
            "live_canary_eligible": True,
        }
    }
    built = SimpleNamespace(
        decision=SimpleNamespace(decision_id="d-1", correlation_id="c-1")
    )
    _record_live_canary_assignment(
        core=core,
        state=state,
        policy=SimpleNamespace(id="candidate@v2"),
        out=SimpleNamespace(action="send_message@v1"),
        built=built,
        tenant_id="tenant-a",
        subject_id="customer-1",
        expected_cost=1.0,
    )
    assert events.rows[-1]["payload"]["arm"] == ExperimentArm.CANDIDATE.value

    with pytest.raises(RuntimeError, match="LIVE_CANARY_ASSIGNMENT_MISMATCH"):
        _record_live_canary_assignment(
            core=core,
            state=state,
            policy=SimpleNamespace(id="active@v1"),
            out=SimpleNamespace(action="send_message@v1"),
            built=SimpleNamespace(
                decision=SimpleNamespace(
                    decision_id="d-2",
                    correlation_id="c-2",
                )
            ),
            tenant_id="tenant-a",
            subject_id="customer-2",
            expected_cost=1.0,
        )


class PolicyEffects(policy_actions.PolicyEffectsMixin):
    def __init__(self) -> None:
        self.event_log = MemoryEvents()
        self.policy_registry = Registry()


def test_policy_effect_allows_one_percent_but_blocks_expansion_without_outcomes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(policy_actions, "assert_called_from_executor", lambda: None)
    monkeypatch.setattr(
        policy_actions,
        "assert_event_log_tenant",
        lambda _event_log, *, tenant_id, operation: tenant_id,
    )
    monkeypatch.setattr(
        policy_actions.RolloutGuard,
        "allow_promotion",
        lambda _metrics: True,
    )
    monkeypatch.setattr(
        policy_actions,
        "DEFAULT_LIVE_CANARY_POLICY",
        live_policy(candidate_pct=1.0),
    )
    effects = PolicyEffects()
    effects.deploy_policy(
        decision_id="deploy-1",
        correlation_id="c-1",
        tenant_id="tenant-a",
        candidate_policy_id="candidate@v2",
        rollout_pct=1,
        experiment_id="metro-followup-2026-08",
    )
    assert effects.policy_registry.calls[-1]["rollout_pct"] == 1

    with pytest.raises(RuntimeError, match="LIVE_CANARY_PROMOTION_BLOCKED"):
        effects.deploy_policy(
            decision_id="deploy-5",
            correlation_id="c-5",
            tenant_id="tenant-a",
            candidate_policy_id="candidate@v2",
            rollout_pct=5,
            experiment_id="metro-followup-2026-08",
        )
