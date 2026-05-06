from __future__ import annotations

from runtime.service_names import RuntimeServiceName

ALLOWED_RUNTIME_SERVICE_NAMES: frozenset[str] = frozenset(
    {
        RuntimeServiceName.OBSERVABILITY,
        RuntimeServiceName.DECISION_INPUT_SERVICE,
        RuntimeServiceName.DECISION_GATEWAY,
        RuntimeServiceName.RUNTIME_STATE_ENRICHMENT,
        RuntimeServiceName.RUNTIME_PACKET_PROVIDER,
        RuntimeServiceName.WORLD_STATE_INTEGRATION,
        RuntimeServiceName.AUTONOMY_ADVISOR,
        RuntimeServiceName.CREATIVE_INTELLIGENCE,
        RuntimeServiceName.MARKET_WATCH,
        RuntimeServiceName.DIFFUSION_WATCH,
        RuntimeServiceName.FLOW_WATCH,
        RuntimeServiceName.STRUCTURE_WATCH,
        RuntimeServiceName.ARCHITECTURE_WATCH,
        RuntimeServiceName.RISK_ENGINE,
        RuntimeServiceName.REWARD_GUARD,
        RuntimeServiceName.SIMULATION_GATE,
        RuntimeServiceName.KILL_SWITCH,
        RuntimeServiceName.ACTION_BUDGET,
        RuntimeServiceName.GOVERNANCE_CHAIN,
        RuntimeServiceName.ACTION_EXECUTOR,
        RuntimeServiceName.DECISION_CORE,
    }
)
