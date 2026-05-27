from __future__ import annotations

from config.decision_safety_policy import (
    AutoDeployerPolicy,
    DecisionValidatorPolicy,
    PolicySelectorPolicy,
    RewardGuardPolicyDefaults,
    RiskScoreGuardPolicy,
    RiskScorerPolicy,
    SafetyProfilePolicy,
)
from config.economics_domain_policy import CapitalAllocationPolicy as EconCapitalAllocationPolicy
from config.economics_domain_policy import LTVEstimatorPolicy
from core.economics.brain import LTVEstimator
from core.economics.capital_allocation_engine import CapitalAllocationEngine, CapitalState, WorldState
from core.math.economics import cac
from core.policies.deployer import AutoDeployer
from core.policies.selector import PolicySelector
from core.policy.decision_validator import DecisionValidator
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlStatus
from core.safety.controls.profile import build_default_profile
from core.safety.controls.reward_guard.guard import RewardGuard
from core.safety.controls.reward_guard.models import RewardGuardPolicy
from core.safety.controls.risk_scoring.guard import RiskScoreGuard
from core.safety.controls.risk_scoring.scorer import RiskScorer


class _Shadow:
    def __init__(self, error: float) -> None:
        self._error = error

    def evaluate(self, dataset, policy):
        return self._error


class _Registry:
    def __init__(self):
        self._items = {"safe": "SAFE", "canary": "CANARY", "main": "MAIN"}

    def active_ref(self):
        return type("Ref", (), {"policy_id": "main"})()

    def canary_ref(self):
        return type("Ref", (), {"policy_id": "canary"})()

    def rollout_config(self):
        return "canary", 150

    def active(self):
        return self._items["main"]

    def get(self, key):
        return self._items[key]


class _State:
    safe_mode = False
    deployment_proposal = None
    meta = {}
    user_id = "u-1"


class _Candidate:
    def __init__(self, *, action_type: str, payload: dict[str, object], confidence: float = 0.9, channel: str = "ok", score: float = 0.5) -> None:
        self.action_type = action_type
        self.payload = payload
        self.confidence = confidence
        self.channel = channel
        self.score = score


class _Constraints:
    min_confidence = 0.1
    max_budget_delta = 100.0
    max_risk_score = 0.9
    forbidden_channels = frozenset({"forbidden"})


def test_ltv_estimator_and_cac_use_policy_zero_defaults() -> None:
    estimator = LTVEstimator(policy=LTVEstimatorPolicy(zero_value=2.0))
    state = type("State", (), {"revenue": 1.0, "cost": 10.0, "retention_prob": 0.5})()
    assert estimator.estimate(state) == 2.0
    assert cac(25.0, 0.0) == 0.0


def test_capital_allocation_engine_uses_policy_owned_floors() -> None:
    policy = EconCapitalAllocationPolicy(
        reserve_ratio=0.1,
        min_runway_days=10,
        shutdown_risk_threshold=0.95,
        reserve_horizon_days=15,
        active_horizon_days=20,
        logistic_floor=-10.0,
        logistic_ceiling=10.0,
        growth_share_min=0.2,
        growth_share_max=0.8,
        zero_value=0.0,
        one_value=1.0,
        runway_days_floor=5.0,
        value_margin_offset=1.0,
    )
    engine = CapitalAllocationEngine(policy=policy)
    capital = CapitalState(cash_balance=1000.0, marketing_budget=300.0, compute_budget=0.0, risk_limits=0.0, runway_days=4.0, reserve=0.0)
    world = WorldState(capital=capital, ltv=200.0, cac=50.0, growth_rate=0.2, churn_rate=0.1, uncertainty=0.1)
    plan = engine.allocate(world)
    assert plan.horizon_days == 15
    assert plan.allocations[0].target == policy.reserve_target
    assert engine.allow_spend(100.0, capital) is True


def test_auto_deployer_and_policy_selector_use_owner_defaults() -> None:
    deployer = AutoDeployer(policy=AutoDeployerPolicy(shadow_threshold=0.3))
    deployer.shadow = _Shadow(0.25)
    assert deployer.approve([], object()) is True

    selector = PolicySelector(_Registry(), policy=PolicySelectorPolicy(rollout_pct_floor=0, rollout_pct_ceiling=100, rollout_pct_divisor=100.0))
    assert selector.resolve_policy(_State()) == "CANARY"


def test_decision_validator_uses_policy_owned_route_lead_floor() -> None:
    validator = DecisionValidator(policy=DecisionValidatorPolicy(route_lead_action_type="route_lead", zero_rank_score=0.0))
    ok, reason = validator.validate(_Candidate(action_type="route_lead", payload={"business_id": "b-1", "rank_score": 0.4}), _Constraints())
    assert ok is True
    ok, reason = validator.validate(_Candidate(action_type="route_lead", payload={"business_id": "b-1", "rank_score": 0.0}), _Constraints())
    assert ok is False
    assert reason == "rank_score_too_low"


def test_reward_and_risk_guards_use_policy_owners() -> None:
    ctx = SafetyActionContext(action="x", tenant_id="t", user_id=None, payload={"expected_reward": -0.1, "expected_margin": 0.2, "amount": 600.0, "audience_size": 150}, metadata={})
    defaults = RewardGuardPolicyDefaults(min_reward=0.0, min_margin=0.0)
    reward_guard = RewardGuard(policy=RewardGuardPolicy(min_reward=defaults.min_reward, min_margin=defaults.min_margin, zero_value=defaults.zero_value))
    reward_decision = reward_guard.evaluate(ctx)
    assert reward_decision.status == ControlStatus.BLOCK

    scorer = RiskScorer(policy=RiskScorerPolicy(amount_threshold=500.0, amount_risk_increment=0.45, audience_size_threshold=100, audience_risk_increment=0.35, review_flag_risk_increment=0.25, score_ceiling=1.0))
    guard = RiskScoreGuard(scorer, policy=RiskScoreGuardPolicy(block_threshold=0.8, review_threshold=0.5))
    risk_decision = guard.evaluate(ctx)
    assert risk_decision.status == ControlStatus.BLOCK


def test_build_default_profile_uses_policy_owned_thresholds() -> None:
    profile = build_default_profile(policy=SafetyProfilePolicy(simulation_gate_min_score=0.6, runaway_loop_repetition_threshold=4))
    assert profile.action_controls.controls
    assert profile.rollback_planner is not None
