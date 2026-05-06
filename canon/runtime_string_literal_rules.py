from __future__ import annotations

from runtime.service_names import RuntimeServiceName

FORBIDDEN_RUNTIME_SERVICE_NAME_LITERALS: tuple[str, ...] = (
    RuntimeServiceName.OBSERVABILITY,
    RuntimeServiceName.RISK_ENGINE,
    RuntimeServiceName.REWARD_GUARD,
    RuntimeServiceName.SIMULATION_GATE,
    RuntimeServiceName.KILL_SWITCH,
    RuntimeServiceName.ACTION_BUDGET,
    RuntimeServiceName.GOVERNANCE_CHAIN,
    RuntimeServiceName.ACTION_EXECUTOR,
    RuntimeServiceName.DECISION_CORE,
)
