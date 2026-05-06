import pytest

from boot.factories.action_executor_factory import build_action_executor
from boot.factories.decision_core_factory import build_decision_core
from boot.factories.governance_chain_factory import build_governance_chain
from boot.registrations.register_action_executor import ActionExecutor
from boot.registrations.register_decision_core import RuntimeDecisionExecutionService
from boot.registrations.register_governance import GovernanceChain


class _Risk:
    def score(self, action: object) -> float:
        return 0.0


class _Reward:
    def validate(self, action: object) -> bool:
        return True


class _Simulation:
    def allow(self, action: object) -> bool:
        return True


class _KillSwitch:
    def allow(self) -> bool:
        return True


class _Budget:
    def allow(self, planned_actions: int) -> bool:
        return True


def test_action_executor_requires_internal_token() -> None:
    with pytest.raises(RuntimeError):
        ActionExecutor(_construction_token=object())

    service = build_action_executor()
    assert service is not None


def test_governance_requires_internal_token() -> None:
    with pytest.raises(RuntimeError):
        GovernanceChain(
            risk_engine=_Risk(),
            reward_guard=_Reward(),
            simulation_gate=_Simulation(),
            kill_switch=_KillSwitch(),
            action_budget=_Budget(),
            _construction_token=object(),
        )

    service = build_governance_chain(
        risk_engine=_Risk(),
        reward_guard=_Reward(),
        simulation_gate=_Simulation(),
        kill_switch=_KillSwitch(),
        action_budget=_Budget(),
    )
    assert service is not None


def test_decision_core_requires_internal_token() -> None:
    executor = build_action_executor()
    governance = build_governance_chain(
        risk_engine=_Risk(),
        reward_guard=_Reward(),
        simulation_gate=_Simulation(),
        kill_switch=_KillSwitch(),
        action_budget=_Budget(),
    )

    with pytest.raises(RuntimeError):
        RuntimeDecisionExecutionService(
            governance_chain=governance,
            action_executor=executor,
            _construction_token=object(),
        )

    service = build_decision_core(
        governance_chain=governance,
        action_executor=executor,
    )
    assert service is not None
