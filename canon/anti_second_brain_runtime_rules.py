from __future__ import annotations

from runtime.service_names import RuntimeServiceName

CANON_ANTI_SECOND_BRAIN_RUNTIME_RULES = True
CANON_RUNTIME_DECISION_EXECUTION_SERVICE_DEPENDENCY_RULES = True

_RUNTIME_DECISION_FORBIDDEN_DEPENDENCIES: tuple[str, ...] = (
    RuntimeServiceName.ARCHITECTURE_WATCH,
    RuntimeServiceName.STRUCTURE_WATCH,
    RuntimeServiceName.FLOW_WATCH,
    RuntimeServiceName.DIFFUSION_WATCH,
    RuntimeServiceName.MARKET_WATCH,
    RuntimeServiceName.CREATIVE_INTELLIGENCE,
    RuntimeServiceName.AUTONOMY_ADVISOR,
    RuntimeServiceName.WORLD_STATE_INTEGRATION,
    RuntimeServiceName.DECISION_INPUT_SERVICE,
    RuntimeServiceName.RISK_ENGINE,
    RuntimeServiceName.REWARD_GUARD,
    RuntimeServiceName.SIMULATION_GATE,
    RuntimeServiceName.KILL_SWITCH,
    RuntimeServiceName.ACTION_BUDGET,
)

FORBIDDEN_DIRECT_DECISION_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE: _RUNTIME_DECISION_FORBIDDEN_DEPENDENCIES,
}

REQUIRED_GOVERNANCE_DEPENDENCIES: tuple[str, ...] = (
    RuntimeServiceName.RISK_ENGINE,
    RuntimeServiceName.REWARD_GUARD,
    RuntimeServiceName.SIMULATION_GATE,
    RuntimeServiceName.KILL_SWITCH,
    RuntimeServiceName.ACTION_BUDGET,
)


__all__ = [
    "CANON_ANTI_SECOND_BRAIN_RUNTIME_RULES",
    "CANON_RUNTIME_DECISION_EXECUTION_SERVICE_DEPENDENCY_RULES",
    "FORBIDDEN_DIRECT_DECISION_DEPENDENCIES",
    "REQUIRED_GOVERNANCE_DEPENDENCIES",
]
