from dataclasses import dataclass, field

from execution.economic_signal_context import EconomicSignalContextBuilder


@dataclass
class _Assessment:
    requested_budget: float = 100.0
    expected_roi: float = 0.5
    runway_days_after_action: float = 120.0


@dataclass
class _Verdict:
    allowed: bool = True
    operator_required: bool = False
    survival_mode: str = "normal"
    reasons: tuple[str, ...] = ("economic_policy_allow",)
    metadata: dict = field(default_factory=lambda: {"approved_budget": 100.0, "requested_budget": 100.0})
    assessment: _Assessment = field(default_factory=_Assessment)


class _Decision:
    action = "launch_campaign"
    payload = {
        "action_type": "launch_campaign",
        "channel": "ads",
        "economy": {"requested_budget": 100.0},
    }


def test_economic_signal_context_prefers_existing_economic_verdict() -> None:
    builder = EconomicSignalContextBuilder()
    signals = builder.build(decision_like=_Decision(), world_state={}, economic_verdict=_Verdict())
    payload = signals.to_decision_context()
    assert payload["budget_allowed"] is True
    assert payload["expected_roi"] == 0.5
    assert payload["metadata"]["source"] == "economic_verdict"
