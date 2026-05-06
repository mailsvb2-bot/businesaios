from __future__ import annotations

from runtime.capabilities import RuntimeCapability
from runtime.service_names import RuntimeServiceName

CAPABILITY_TO_ALLOWED_SERVICES: dict[str, tuple[str, ...]] = {
    RuntimeCapability.BOOT_OBSERVABILITY: (
        RuntimeServiceName.OBSERVABILITY,
    ),
    RuntimeCapability.GOVERNANCE_COMPONENTS: (
        RuntimeServiceName.RISK_ENGINE,
        RuntimeServiceName.REWARD_GUARD,
        RuntimeServiceName.SIMULATION_GATE,
        RuntimeServiceName.KILL_SWITCH,
        RuntimeServiceName.ACTION_BUDGET,
    ),
    RuntimeCapability.DECISION_EXECUTION: (
        RuntimeServiceName.GOVERNANCE_CHAIN,
        RuntimeServiceName.ACTION_EXECUTOR,
    ),
    RuntimeCapability.READ_DECISION_CORE: (
        RuntimeServiceName.DECISION_CORE,
    ),
}
