from __future__ import annotations

from boot.registrations.register_governance import GovernanceChain
from runtime.constructor_tokens import runtime_construction_token


class _Risk:
    def __init__(self, value: float) -> None:
        self._value = value

    def score(self, action):
        return self._value


class _Reward:
    def validate(self, action):
        return True


class _Simulation:
    def allow(self, action):
        return True


class _Kill:
    def allow(self):
        return True


class _Budget:
    def allow(self, action):
        return action.get('planned_actions', 1) <= 2


def test_governance_chain_blocks_when_payload_budget_exceeds_limit() -> None:
    chain = GovernanceChain(
        risk_engine=_Risk(0.1),
        reward_guard=_Reward(),
        simulation_gate=_Simulation(),
        kill_switch=_Kill(),
        action_budget=_Budget(),
        _construction_token=runtime_construction_token(),
    )
    assert chain.evaluate({'planned_actions': 3}) is False


def test_governance_chain_respects_payload_risk_threshold() -> None:
    chain = GovernanceChain(
        risk_engine=_Risk(0.9),
        reward_guard=_Reward(),
        simulation_gate=_Simulation(),
        kill_switch=_Kill(),
        action_budget=_Budget(),
        _construction_token=runtime_construction_token(),
    )
    assert chain.evaluate({'max_allowed_risk_score': 0.5}) is False
    assert chain.evaluate({'max_allowed_risk_score': 0.95}) is True
