from __future__ import annotations

from dataclasses import replace
import time
from types import SimpleNamespace

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.assignment import StableExperimentAssigner
from core.experiments.guardrails import CanaryDecision, GuardrailResult
from core.experiments.ledger import LiveCanaryLedger
from core.policies.selector import PolicySelector
from runtime._internal.effects_actions import policy_actions
from runtime.experiments.live_canary import LiveCanaryCoordinator
from runtime.boot import boot_decision_core
from runtime.experiments.watchdog import LiveCanaryWatchdog


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
    def __init__(self, rollout_pct: int = 0) -> None:
        self.candidate_policy_id = "candidate@v2"
        self.rollout_pct = rollout_pct
        self.calls: list[dict] = []

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")

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


def policy(**overrides) -> LiveCanaryPolicy:
    base = LiveCanaryPolicy(
        enabled=True,
        experiment_id="review-closure-canary",
        assignment_secret="v" * 32,
        candidate_pct=1.0,
        max_candidate_pct=10.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_purposes=("live_canary",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        max_candidate_actions_per_day=10_000,
        max_candidate_actions_per_subject_24h=1,
        max_daily_cost=10_000.0,
        min_assignments=100_000,
        min_candidate_assignments=100,
        min_outcomes_per_arm=100,
        min_duration_seconds=60,
        outcome_window_seconds=60,
    )
    return replace(base, **overrides)


class PolicyEffects(policy_actions.PolicyEffectsMixin):
    def __init__(self) -> None:
        self.event_log = MemoryEvents()
        self.policy_registry = Registry()


def test_deploy_derives_configured_experiment_without_new_action_field(
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
    configured = policy(max_candidate_pct=1.0)
    monkeypatch.setattr(
        policy_actions,
        "DEFAULT_LIVE_CANARY_POLICY",
        configured,
    )
    effects = PolicyEffects()
    effects.deploy_policy(
        decision_id="deploy-1",
        correlation_id="c-1",
        tenant_id="tenant-a",
        candidate_policy_id="candidate@v2",
        rollout_pct=1,
    )
    deployed = effects.event_log.get_events("deploy-1", "policy_deployed")[-1]
    assert deployed["payload"]["experiment_id"] == configured.experiment_id
    assert effects.policy_registry.rollout_pct == 1


class SelectorRegistry:
    def __init__(self) -> None:
        self.active_policy = SimpleNamespace(id="active@v1")
        self.candidate_policy = SimpleNamespace(id="candidate@v2")

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")

    def canary_ref(self):
        return SimpleNamespace(policy_id="candidate@v2")

    def active(self):
        return self.active_policy

    def get(self, policy_id):
        return (
            self.candidate_policy
            if str(policy_id) == "candidate@v2"
            else self.active_policy
        )

    def rollout_config(self):
        return "candidate@v2", 100


def test_selector_uses_canonical_product_tenant_and_nested_actor() -> None:
    selector = PolicySelector(SelectorRegistry())
    selector._resolver.live_policy = policy(
        candidate_pct=100.0,
        max_candidate_pct=100.0,
    )
    state = {
        "product_metadata": {"tenant_id": "tenant-a"},
        "user": {"actor_id": "customer-1"},
        "meta": {
            "purpose": "live_canary",
            "live_canary_eligible": True,
        },
    }
    assert selector.resolve_policy(state).id == "candidate@v2"
    assert selector.resolve_policy({**state, "user": {}}).id == "active@v1"


def test_coordinator_uses_registry_rollout_not_boot_percentage() -> None:
    coordinator = LiveCanaryCoordinator(
        event_log=MemoryEvents(),
        policy_registry=Registry(rollout_pct=5),
        candidate_policy_id="candidate@v2",
        policy=policy(candidate_pct=1.0, max_candidate_pct=10.0),
    )
    assert coordinator._effective_policy().candidate_pct == 5.0


def test_watchdog_submits_rollback_without_mutating_registry_directly() -> None:
    registry = Registry(rollout_pct=5)
    coordinator = LiveCanaryCoordinator(
        event_log=MemoryEvents(),
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=policy(candidate_pct=5.0, max_candidate_pct=10.0),
    )
    rollback = GuardrailResult(
        CanaryDecision.ROLLBACK,
        ("critical_violation",),
        {"critical_violations": 1},
    )
    coordinator._guard_result = lambda: rollback
    submitted = {}
    watchdog = LiveCanaryWatchdog(
        coordinator,
        tenant_id="tenant-a",
        rollback_submitter=lambda **kwargs: submitted.update(kwargs),
        interval_seconds=1,
    )
    result = watchdog.run_once()
    assert result is rollback
    assert submitted["candidate_policy_id"] == "candidate@v2"
    assert submitted["reasons"] == ("critical_violation",)
    assert registry.rollout_pct == 5
    assert registry.calls == []
    assert coordinator.rollback_required is True


def test_full_promotion_disables_canary_assignment() -> None:
    registry = Registry(rollout_pct=0)
    registry.candidate_policy_id = None
    coordinator = LiveCanaryCoordinator(
        event_log=MemoryEvents(),
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=policy(candidate_pct=10.0, max_candidate_pct=100.0),
    )
    assert coordinator.live_rollout_pct() == 0.0
    result = coordinator._guard_result()
    assert result.decision is CanaryDecision.CONTINUE
    assert result.reasons == ("rollout_inactive",)


def test_rolling_safety_budget_spans_all_rollout_stages() -> None:
    events = MemoryEvents()
    ledger = LiveCanaryLedger(
        events,
        experiment_id="review-closure-canary",
        candidate_policy_id="candidate@v2",
        outcome_window_seconds=60,
    )
    now_ms = int(time.time() * 1000)
    for index, candidate_pct in enumerate((1.0, 5.0), start=1):
        stage_policy = policy(
            candidate_pct=100.0,
            max_candidate_pct=100.0,
        )
        assignment = StableExperimentAssigner(stage_policy).assign(
            tenant_id="tenant-a",
            subject_id="same-customer",
            candidate_policy_id="candidate@v2",
            action="send_message@v1",
            purpose="live_canary",
            eligible=True,
        )
        ledger.record_assignment(
            assignment,
            decision_id=f"stage-{index}",
            correlation_id=f"c-{index}",
            production_policy_id="active@v1",
            action="send_message@v1",
            candidate_pct=candidate_pct,
            expected_cost=6.0,
            assigned_at_ms=now_ms - index,
        )
    metrics = ledger.metrics(candidate_pct=5.0)
    assert metrics["assignment_count"] == 1
    assert metrics["candidate_actions_24h"] == 2
    assert metrics["candidate_expected_cost_24h"] == 12.0
    assert metrics["candidate_max_actions_per_subject_24h"] == 2


def test_selector_rejects_meta_only_tenant_for_live_canary() -> None:
    selector = PolicySelector(SelectorRegistry())
    selector._resolver.live_policy = policy(
        candidate_pct=100.0,
        max_candidate_pct=100.0,
    )
    state = {
        "user_id": "customer-1",
        "meta": {
            "tenant_id": "tenant-a",
            "purpose": "live_canary",
            "live_canary_eligible": True,
        },
    }
    assert selector.resolve_policy(state).id == "active@v1"


def test_boot_starts_automatic_outcome_supervisor(monkeypatch) -> None:
    configured = policy(outcome_poll_seconds=1.0)
    monkeypatch.setattr(
        boot_decision_core,
        "DEFAULT_LIVE_CANARY_POLICY",
        configured,
    )
    calls: list[str] = []
    monkeypatch.setattr(
        boot_decision_core,
        "attach_live_canary",
        lambda core, **_kwargs: calls.append("attach"),
    )
    monkeypatch.setattr(
        boot_decision_core,
        "start_live_canary_runtime",
        lambda core: calls.append("start"),
    )
    selector = SimpleNamespace(
        _registry=SimpleNamespace(
            rollout_config=lambda: ("candidate@v2", 1),
        )
    )
    boot_decision_core._attach_configured_live_canary(
        SimpleNamespace(), selector
    )
    assert calls == ["attach", "start"]
