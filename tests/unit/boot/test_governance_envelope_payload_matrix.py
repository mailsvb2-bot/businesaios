from __future__ import annotations

import itertools
from types import SimpleNamespace

from boot.factories.governance_chain_factory import build_governance_chain
from boot.registrations.simple_singletons import ActionBudget, KillSwitch, RewardGuard, RiskEngine, SimulationGate


def test_real_decision_envelope_payload_reaches_every_governance_gate() -> None:
    for kill_ok, reward_ok, simulation_ok, budget_ok, risk_ok in itertools.product((False, True), repeat=5):
        envelope = SimpleNamespace(
            decision=SimpleNamespace(
                action="send_message@v1",
                payload={
                    "expected_reward": 0.0 if reward_ok else -1.0,
                    "expected_margin": 0.0,
                    "requires_simulation": True,
                    "simulation_passed": simulation_ok,
                    "planned_actions": 1 if budget_ok else 1001,
                    "risk_score": 0.1 if risk_ok else 0.9,
                    "max_allowed_risk_score": 0.8,
                },
            )
        )
        chain = build_governance_chain(
            risk_engine=RiskEngine(),
            reward_guard=RewardGuard(),
            simulation_gate=SimulationGate(),
            kill_switch=KillSwitch(is_stopped=not kill_ok),
            action_budget=ActionBudget(max_actions=1000),
        )
        assert chain.evaluate(envelope) is (kill_ok and reward_ok and simulation_ok and budget_ok and risk_ok)
