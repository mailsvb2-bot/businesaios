from __future__ import annotations

from runtime.service_names import RuntimeServiceName

FORBIDDEN_DIRECT_DECISION_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    RuntimeServiceName.DECISION_CORE: (
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
    ),
}

REQUIRED_GOVERNANCE_DEPENDENCIES: tuple[str, ...] = (
    RuntimeServiceName.RISK_ENGINE,
    RuntimeServiceName.REWARD_GUARD,
    RuntimeServiceName.SIMULATION_GATE,
    RuntimeServiceName.KILL_SWITCH,
    RuntimeServiceName.ACTION_BUDGET,
)
