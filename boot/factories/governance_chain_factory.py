from __future__ import annotations

from boot.registrations.register_governance import GovernanceChain
from runtime.constructor_tokens import runtime_construction_token


def build_governance_chain(*, risk_engine: object, reward_guard: object, simulation_gate: object, kill_switch: object, action_budget: object) -> GovernanceChain:
    return GovernanceChain(
        risk_engine=risk_engine,
        reward_guard=reward_guard,
        simulation_gate=simulation_gate,
        kill_switch=kill_switch,
        action_budget=action_budget,
        _construction_token=runtime_construction_token(),
    )


__all__ = ["build_governance_chain"]
