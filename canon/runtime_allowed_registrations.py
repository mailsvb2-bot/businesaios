from __future__ import annotations

from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType

ALLOWED_RUNTIME_REGISTRATIONS: dict[str, str] = {
    RuntimeServiceName.OBSERVABILITY: RuntimeServiceType.GUARD,
    RuntimeServiceName.ARCHITECTURE_WATCH: RuntimeServiceType.GUARD,
    RuntimeServiceName.STRUCTURE_WATCH: RuntimeServiceType.GUARD,
    RuntimeServiceName.FLOW_WATCH: RuntimeServiceType.GUARD,
    RuntimeServiceName.DIFFUSION_WATCH: RuntimeServiceType.GUARD,
    RuntimeServiceName.MARKET_WATCH: RuntimeServiceType.GUARD,
    RuntimeServiceName.CREATIVE_INTELLIGENCE: RuntimeServiceType.GUARD,
    RuntimeServiceName.AUTONOMY_ADVISOR: RuntimeServiceType.GOVERNANCE,
    RuntimeServiceName.WORLD_STATE_INTEGRATION: RuntimeServiceType.GOVERNANCE,
    RuntimeServiceName.DECISION_INPUT_SERVICE: RuntimeServiceType.GOVERNANCE,
    RuntimeServiceName.RUNTIME_PACKET_PROVIDER: RuntimeServiceType.GOVERNANCE,
    RuntimeServiceName.RUNTIME_STATE_ENRICHMENT: RuntimeServiceType.GOVERNANCE,
    RuntimeServiceName.DECISION_GATEWAY: RuntimeServiceType.GOVERNANCE,
    RuntimeServiceName.RISK_ENGINE: RuntimeServiceType.GUARD,
    RuntimeServiceName.REWARD_GUARD: RuntimeServiceType.GUARD,
    RuntimeServiceName.SIMULATION_GATE: RuntimeServiceType.GUARD,
    RuntimeServiceName.KILL_SWITCH: RuntimeServiceType.GUARD,
    RuntimeServiceName.ACTION_BUDGET: RuntimeServiceType.GUARD,
    RuntimeServiceName.GOVERNANCE_CHAIN: RuntimeServiceType.GOVERNANCE,
    RuntimeServiceName.ACTION_EXECUTOR: RuntimeServiceType.EXECUTOR,
    RuntimeServiceName.DECISION_CORE: RuntimeServiceType.CORE,
}
