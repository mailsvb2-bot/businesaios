from __future__ import annotations

from dataclasses import dataclass, field

from execution.policy_explainer import PolicyExplainer


@dataclass
class StubDecision:
    policy_id: str = "policy-1"
    action: str = "ACTION_EXECUTE_PLAN_V1"


@dataclass
class StubEnvelope:
    decision: StubDecision = field(default_factory=StubDecision)


@dataclass
class StubState:
    meta: dict | None = None
    behavior: dict | None = None

    def __post_init__(self) -> None:
        if self.meta is None:
            self.meta = {
                "goal": "get 10 clients",
                "constraints": {"budget_cap_daily": 50},
                "signals": [{"kind": "lead_velocity", "value": 3}],
                "previous_feedback": {"goal_score": 0.4},
                "profile": {"segment": "local_services"},
            }
        if self.behavior is None:
            self.behavior = {"goal": "get 10 clients"}


def test_policy_explainer_emits_summary_and_factors() -> None:
    explainer = PolicyExplainer()
    explanation = explainer.explain(
        state=StubState(),
        envelope=StubEnvelope(),
    )
    assert explanation.policy_id == "policy-1"
    assert "ACTION_EXECUTE_PLAN_V1" in explanation.summary
    assert "constraints_present" in explanation.factors
    assert "signals_present" in explanation.factors
    assert "goal:get 10 clients" in explanation.factors
    assert "capability_class:internal_execution" in explanation.factors
    assert "capability_not_externally_verified" in explanation.factors
