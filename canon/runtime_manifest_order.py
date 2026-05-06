from __future__ import annotations

from runtime.service_names import RuntimeServiceName

CANONICAL_RUNTIME_MANIFEST_ORDER: tuple[str, ...] = (
    RuntimeServiceName.OBSERVABILITY,
    RuntimeServiceName.ARCHITECTURE_WATCH,
    RuntimeServiceName.STRUCTURE_WATCH,
    RuntimeServiceName.FLOW_WATCH,
    RuntimeServiceName.DIFFUSION_WATCH,
    RuntimeServiceName.MARKET_WATCH,
    RuntimeServiceName.CREATIVE_INTELLIGENCE,
    RuntimeServiceName.AUTONOMY_ADVISOR,
    RuntimeServiceName.WORLD_STATE_INTEGRATION,
    RuntimeServiceName.DECISION_INPUT_SERVICE,
    RuntimeServiceName.RUNTIME_PACKET_PROVIDER,
    RuntimeServiceName.RUNTIME_STATE_ENRICHMENT,
    RuntimeServiceName.DECISION_GATEWAY,
    RuntimeServiceName.RISK_ENGINE,
    RuntimeServiceName.REWARD_GUARD,
    RuntimeServiceName.SIMULATION_GATE,
    RuntimeServiceName.KILL_SWITCH,
    RuntimeServiceName.ACTION_BUDGET,
    RuntimeServiceName.GOVERNANCE_CHAIN,
    RuntimeServiceName.ACTION_EXECUTOR,
    RuntimeServiceName.DECISION_CORE,
)
