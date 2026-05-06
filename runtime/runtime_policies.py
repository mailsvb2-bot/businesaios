from __future__ import annotations

from dataclasses import dataclass

from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


@dataclass(frozen=True)
class RuntimePolicies:
    allowed_service_types: tuple[str, ...] = (
        RuntimeServiceType.GUARD,
        RuntimeServiceType.GOVERNANCE,
        RuntimeServiceType.EXECUTOR,
        RuntimeServiceType.CORE,
    )

    required_services: tuple[str, ...] = (
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
        RuntimeServiceName.RISK_ENGINE,
        RuntimeServiceName.REWARD_GUARD,
        RuntimeServiceName.SIMULATION_GATE,
        RuntimeServiceName.KILL_SWITCH,
        RuntimeServiceName.ACTION_BUDGET,
        RuntimeServiceName.GOVERNANCE_CHAIN,
        RuntimeServiceName.ACTION_EXECUTOR,
        RuntimeServiceName.DECISION_CORE,
    )
