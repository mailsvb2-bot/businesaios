from __future__ import annotations

from boot.registrations._shared import register_runtime_service
from boot.runtime_dependency_sets import GOVERNANCE_CHAIN_DEPS
from boot.runtime_service_contracts import GovernanceChain
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


def register_governance(registry: RuntimeRegistry):
    from boot.factories.governance_chain_factory import build_governance_chain

    service = build_governance_chain(
        risk_engine=registry.get(RuntimeServiceName.RISK_ENGINE),
        reward_guard=registry.get(RuntimeServiceName.REWARD_GUARD),
        simulation_gate=registry.get(RuntimeServiceName.SIMULATION_GATE),
        kill_switch=registry.get(RuntimeServiceName.KILL_SWITCH),
        action_budget=registry.get(RuntimeServiceName.ACTION_BUDGET),
    )
    return register_runtime_service(
        registry,
        name=RuntimeServiceName.GOVERNANCE_CHAIN,
        service=service,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=GOVERNANCE_CHAIN_DEPS,
    )


__all__ = ["GovernanceChain", "register_governance"]
