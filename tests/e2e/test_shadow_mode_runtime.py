from __future__ import annotations

from types import SimpleNamespace

import pytest

import application.decision_runtime.run as decision_run
from config.staged_rollout_policy import StagedRolloutPolicy
from core.events.event_types import (
    SHADOW_DECISION_EVALUATED,
    SHADOW_OUTCOME_ATTRIBUTED,
    SHADOW_PRODUCTION_OUTCOME_OBSERVED,
    is_known,
)
from core.policies.selector import PolicySelector
from core.policies.shadow import ShadowDecisionLedger, ShadowEvaluator
from core.policies.staged_rollout import RolloutGuard, RolloutStage, StagedRollout
from core.reward.reward_engine import RewardEngine
from runtime._internal.effects_actions import policy_actions


class MemoryEvents:
    tenant_id = "t-1"

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(self, *, event_type, source, user_id, payload, decision_id=None, correlation_id=None, **_kwargs):
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
        return [row for row in self.rows if row["decision_id"] == decision_id and row["event_type"] == event_type]

    def iter_events(self):
        return iter(self.rows)

    def has_event(self, decision_id, event_type):
        return bool(self.get_events(decision_id, event_type))


class Schemas:
    def validate(self, action, payload):
        if action == "invalid@v1":
            raise ValueError("invalid")
        return 1


class Candidate:
    __module__ = "core.policies.shadow_candidate_fixture"
    id = "candidate@v2"

    def __init__(self, *, action="send_message@v1") -> None:
        self.action = action

    def propose(self, state):
        state["mutated"] = True
        return SimpleNamespace(
            action=self.action,
            payload={"expected_reward": 2.0, "expected_cost": 3.0, "risk_score": 0.1},
        )


def envelope(*, action="noop@v1", decision_id="d-1"):
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=decision_id,
            correlation_id="c-1",
            policy_id="active@v1",
            action=action,
            payload={"actor_id": "u-1", "expected_cost": 1.0, "amount": 100.0},
            issued_at_ms=0,
            snapshot_id="s-1",
        )
    )


def test_shadow_observation_uses_copy_and_never_describes_an_effect() -> None:
    events = MemoryEvents()
    evaluator = ShadowEvaluator(ShadowDecisionLedger(events), Schemas())
    state = {"value": 1}

    row = evaluator.observe(state, envelope(), Candidate())

    assert state == {"value": 1}
    assert row["candidate_action"] == "send_message@v1"
    assert row["candidate_payload_hash"]
    assert row["simulation"] is True
    assert row["observe_only"] is True
    assert row["writes_outbox"] is False
    assert row["external_effect"] is False
    assert events.rows[0]["event_type"] == SHADOW_DECISION_EVALUATED


def test_shadow_failures_are_evidence_not_production_failures() -> None:
    events = MemoryEvents()
    evaluator = ShadowEvaluator(ShadowDecisionLedger(events), Schemas())
    row = evaluator.observe({}, envelope(), Candidate(action="invalid@v1"))
    assert row["schema_error"] == "ValueError"
    assert row["status"] == "invalid"

    class BrokenEvents(MemoryEvents):
        def emit(self, **_kwargs):
            raise OSError("storage unavailable")

    row = ShadowEvaluator(ShadowDecisionLedger(BrokenEvents()), Schemas()).observe({}, envelope(), Candidate())
    assert row["status"] == "evaluated"


def test_outcome_attribution_is_explicit_and_event_backed() -> None:
    events = MemoryEvents()
    evaluator = ShadowEvaluator(ShadowDecisionLedger(events), Schemas())
    evaluator.observe({}, envelope(), Candidate())
    production = evaluator.record_production_outcome("d-1", actual_reward=1.0)
    before = evaluator.metrics()
    outcome = evaluator.attribute_counterfactual(
        "d-1", candidate_reward=1.5, evaluator_id="causal-replay@v1", evidence_ref="replay:1"
    )
    metrics = evaluator.metrics()

    assert production["counterfactual"] is False
    assert before["production_outcome_count"] == 1
    assert before["outcome_count"] == 0
    assert outcome["regret"] == 0.5
    assert outcome["counterfactual"] is True
    assert events.rows[-1]["event_type"] == SHADOW_OUTCOME_ATTRIBUTED
    assert metrics["decision_count"] == 1
    assert metrics["production_outcome_count"] == 1
    assert metrics["outcome_count"] == 1
    assert metrics["critical_violations"] == 0
    assert metrics["average_cost_increase"] == 2.0
    assert is_known(SHADOW_DECISION_EVALUATED)
    assert is_known(SHADOW_PRODUCTION_OUTCOME_OBSERVED)
    assert is_known(SHADOW_OUTCOME_ATTRIBUTED)


def test_promotion_gate_is_fail_closed_and_requires_outcomes() -> None:
    policy = StagedRolloutPolicy(
        min_shadow_decisions=2,
        min_production_outcomes=2,
        min_outcome_observations=2,
        max_disagreement_rate=0.5,
        max_average_cost_increase=1.0,
        max_average_regret=0.1,
        max_p95_latency_ms=50.0,
    )
    good = {
        "decision_count": 2,
        "production_outcome_count": 2,
        "outcome_count": 2,
        "error_rate": 0.0,
        "disagreement_rate": 0.5,
        "critical_violations": 0,
        "average_cost_increase": 1.0,
        "average_regret": 0.1,
        "p95_latency_ms": 50.0,
    }
    assert RolloutGuard.allow_promotion(good, policy=policy) is True
    assert RolloutGuard.allow_promotion({**good, "critical_violations": 1}, policy=policy) is False
    assert RolloutGuard.allow_promotion({}, policy=policy) is False
    runner = SimpleNamespace(run=lambda *_args: good)
    assert StagedRollout(runner, policy).evaluate(has_offline_candidate=True, policy=object(), live_stream=()) is RolloutStage.PROD
    assert StagedRollout(runner, policy).evaluate(has_offline_candidate=False, policy=object(), live_stream=()) is RolloutStage.OFFLINE


def test_policy_selector_exposes_configured_candidate_only_beside_active() -> None:
    candidate = Candidate()
    registry = SimpleNamespace(rollout_config=lambda: (candidate.id, 0), maybe_get=lambda policy_id: candidate if policy_id == candidate.id else None)
    selector = PolicySelector.__new__(PolicySelector)
    selector._registry = registry
    assert selector.resolve_shadow_policy({}, production_policy_id="active@v1") is candidate
    assert selector.resolve_shadow_policy({}, production_policy_id=candidate.id) is None
    selector._registry = SimpleNamespace(rollout_config=lambda: (candidate.id, 10), maybe_get=lambda _policy_id: candidate)
    assert selector.resolve_shadow_policy({}, production_policy_id="active@v1") is None


def test_reward_engine_records_only_the_real_production_outcome() -> None:
    events = MemoryEvents()
    events.emit(
        event_type=SHADOW_DECISION_EVALUATED,
        source="shadow_mode",
        user_id="u-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={"production_action": "capture_payment@v1", "candidate_action": "noop@v1", "candidate_expected_reward": 2.0},
    )
    events.emit(
        event_type="payment_captured",
        source="test",
        user_id="u-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={"ok": True},
    )
    reward = RewardEngine(event_log=events).observe(envelope(action="capture_payment@v1"), {"amount": 100.0})
    assert reward == 1.0
    observed = events.get_events("d-1", SHADOW_PRODUCTION_OUTCOME_OBSERVED)
    assert observed[0]["payload"]["actual_reward"] == 1.0
    assert events.get_events("d-1", SHADOW_OUTCOME_ATTRIBUTED) == []


class RuntimePolicyRegistry:
    def __init__(self) -> None:
        self.calls = []

    def snapshot_runtime_state(self):
        return tuple(self.calls)

    def restore_runtime_state(self, snapshot):
        self.calls = list(snapshot)

    def set_rollout(self, **kwargs):
        self.calls.append(dict(kwargs))


class PolicyEffects(policy_actions.PolicyEffectsMixin):
    def __init__(self) -> None:
        self.event_log = MemoryEvents()
        self.policy_registry = RuntimePolicyRegistry()


def test_sealed_deploy_effect_requires_shadow_evidence(monkeypatch) -> None:
    monkeypatch.setattr(policy_actions, "assert_called_from_executor", lambda: None)
    effects = PolicyEffects()
    effects.deploy_policy(decision_id="d-shadow", correlation_id="c-shadow", tenant_id="t-1", candidate_policy_id="candidate@v2", rollout_pct=0)
    assert effects.policy_registry.calls[-1]["rollout_pct"] == 0
    with pytest.raises(RuntimeError, match="SHADOW_PROMOTION_BLOCKED"):
        effects.deploy_policy(decision_id="d-canary", correlation_id="c-canary", tenant_id="t-1", candidate_policy_id="candidate@v2", rollout_pct=10)

    seen = {}
    monkeypatch.setattr(policy_actions.RolloutGuard, "allow_promotion", lambda metrics: seen.update(metrics) or True)
    effects.deploy_policy(decision_id="d-canary", correlation_id="c-canary", tenant_id="t-1", candidate_policy_id="candidate@v2", rollout_pct=10)
    assert effects.policy_registry.calls[-1]["rollout_pct"] == 10
    assert seen["decision_count"] == 0


class FakeSpan:
    def __init__(self, **_kwargs):
        self.extra = {}
        self._t0_ns = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_canonical_decision_run_invokes_shadow_on_enriched_constrained_state(monkeypatch) -> None:
    production = SimpleNamespace(id="active@v1")
    selected = SimpleNamespace(action="noop@v1", payload={})
    built_envelope = envelope()
    observed = {}
    core = SimpleNamespace(
        _world_model=object(),
        _issuer_id="issuer",
        _events=MemoryEvents(),
        _schemas=Schemas(),
        _keyring=object(),
        _ttl_ms=1,
        _archive=None,
        _snapshots=SimpleNamespace(put=lambda *_args: None),
        _selector=object(),
        observe_shadow=lambda **kwargs: observed.update(kwargs),
    )
    monkeypatch.setattr(decision_run, "Span", FakeSpan)
    monkeypatch.setattr(decision_run, "enrich_state_with_world_model", lambda **_kwargs: {"stage": "enriched"})
    monkeypatch.setattr(decision_run, "build_trace", lambda **_kwargs: ("u-1", SimpleNamespace(), {}))
    monkeypatch.setattr(decision_run, "apply_state_constraints", lambda **_kwargs: {"stage": "constrained"})
    monkeypatch.setattr(decision_run, "select_and_propose", lambda **_kwargs: (production, selected))
    monkeypatch.setattr(decision_run, "_emit_router_sla", lambda **_kwargs: None)
    monkeypatch.setattr(decision_run, "extract_product_metadata", lambda _state: ({}, "", "", ""))
    monkeypatch.setattr(decision_run, "extract_tenant_id", lambda _state: "t-1")
    monkeypatch.setattr(decision_run, "extract_actor_id", lambda _state: "u-1")
    monkeypatch.setattr(decision_run, "build_payload", lambda **_kwargs: ({}, {}))
    monkeypatch.setattr(decision_run, "validate_and_gate_action", lambda **_kwargs: 1)
    monkeypatch.setattr(decision_run, "build_envelope", lambda **_kwargs: SimpleNamespace(envelope=built_envelope, decision=built_envelope.decision, state_bytes=b"{}"))
    monkeypatch.setattr(decision_run, "build_archive_envelope", lambda **_kwargs: built_envelope)
    monkeypatch.setattr(decision_run, "archive_envelope_safe", lambda **_kwargs: None)
    monkeypatch.setattr(decision_run, "emit_decision_issued", lambda **_kwargs: None)
    monkeypatch.setattr(decision_run, "emit_world_model_pinned", lambda **_kwargs: None)
    monkeypatch.setattr(decision_run, "emit_trace", lambda **_kwargs: None)

    result = decision_run.run_decision(core=core, state={"stage": "raw"}, envelope_version=1, logger=object())

    assert result is built_envelope
    assert observed["state"] == {"stage": "constrained"}
    assert observed["production_envelope"] is built_envelope
    assert observed["production_policy_id"] == production.id


def test_decision_core_owns_shadow_candidate_resolution() -> None:
    from core.ai.decision_core import DecisionCore

    candidate = Candidate()
    observed = {}
    core = DecisionCore.__new__(DecisionCore)
    core._selector = SimpleNamespace(resolve_shadow_policy=lambda state, production_policy_id: candidate)
    core._shadow_observer = SimpleNamespace(observe=lambda **kwargs: observed.update(kwargs) or kwargs)
    result = core.observe_shadow(state={"x": 1}, production_envelope=envelope(), production_policy_id="active@v1")
    assert result["candidate_policy"] is candidate
    assert observed["state"] == {"x": 1}


def test_shadow_selector_rejects_foreign_policy_object() -> None:
    foreign = SimpleNamespace(id="foreign@v1")
    registry = SimpleNamespace(rollout_config=lambda: (foreign.id, 0), maybe_get=lambda _policy_id: foreign)
    selector = PolicySelector.__new__(PolicySelector)
    selector._registry = registry
    assert selector.resolve_shadow_policy({}, production_policy_id="active@v1") is None


def test_shadow_registration_is_not_canary_activation(monkeypatch) -> None:
    import core.ai.policy_registry as registry_module

    monkeypatch.setattr(registry_module, "assert_called_from_bootstrap", lambda: None)
    monkeypatch.setattr(registry_module, "assert_called_from_runtime_executor", lambda: None)
    registry = registry_module.PolicyRegistry()
    registry.register(SimpleNamespace(id="active@v1"))
    registry.register(SimpleNamespace(id="candidate@v2"))
    registry.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=0)
    assert registry.rollout_config() == ("candidate@v2", 0)
    assert registry.canary_ref() is None


def test_counterfactual_reward_requires_governed_evidence() -> None:
    evaluator = ShadowEvaluator(ShadowDecisionLedger(MemoryEvents()), Schemas())
    evaluator.observe({}, envelope(), Candidate())
    evaluator.record_production_outcome("d-1", 1.0)
    assert evaluator.attribute_counterfactual("d-1", 2.0, evaluator_id="", evidence_ref="replay:1") is None
    assert evaluator.attribute_counterfactual("d-1", 2.0, evaluator_id="causal@v1", evidence_ref="") is None
    assert evaluator.metrics()["outcome_count"] == 0
