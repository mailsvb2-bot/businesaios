from __future__ import annotations

import pytest

from governance.constitution import Constitution, ConstitutionViolation
from governance.evolution_gate import EvolutionGate, EvolutionRejected, PolicyMetrics
from governance.self_driving_loop import PolicyMetrics as LoopMetrics
from governance.self_driving_loop import RollbackController, SelfDrivingLoop
from governance.survival_controller import GovernanceHealthState, SurvivalController


def test_constitution_rejects_parallel_decision_brain() -> None:
    constitution = Constitution()
    with pytest.raises(ConstitutionViolation, match="Parallel decision brain forbidden"):
        constitution.assert_no_parallel_decision_brain(has_parallel_brain=True)


def test_survival_controller_rolls_back_only_in_critical_state() -> None:
    controller = SurvivalController()
    assert controller.assess(reward_drop=0.2, error_rate=0.0) == GovernanceHealthState.DEGRADED
    assert controller.should_rollback() is False
    assert controller.assess(reward_drop=0.0, error_rate=0.5) == GovernanceHealthState.CRITICAL
    assert controller.should_rollback() is True


def test_self_driving_loop_rolls_back_when_survival_controller_is_critical() -> None:
    class _Store:
        def all(self):
            return [1.0, 2.0, 3.0]

    class _Trainer:
        def train(self, rewards):
            return {"policy": "new"}

    class _Eval:
        def evaluate(self, policy, rewards):
            return LoopMetrics(reward=1.0, risk=0.0, stability=1.0)

    class _Registry:
        def __init__(self):
            self._active = {"policy": "old"}

        @property
        def active(self):
            return self._active

        def swap(self, policy):
            self._active = policy

    class _Rollout:
        def approve(self, old, new):
            return True

    survival = SurvivalController()
    survival.assess(reward_drop=0.0, error_rate=0.5)
    reg = _Registry()
    rb = RollbackController(reg)
    loop = SelfDrivingLoop(_Store(), _Trainer(), _Eval(), reg, _Rollout(), rb, survival_controller=survival)
    report = loop.evolve_once()
    assert report.evolved is False
    assert report.rollback_triggered is True
    assert reg.active["policy"] == "old"


def test_evolution_gate_rejects_large_reward_regression() -> None:
    gate = EvolutionGate()
    with pytest.raises(EvolutionRejected, match="Reward gain too small|Reward regression too large"):
        gate.approve(
            PolicyMetrics(reward=1.0, risk=0.01, stability=0.99),
            PolicyMetrics(reward=0.7, risk=0.01, stability=0.99),
        )
