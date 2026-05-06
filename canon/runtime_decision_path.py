from __future__ import annotations

from runtime.service_names import RuntimeServiceName

CANONICAL_RUNTIME_DECISION_PATH: tuple[str, ...] = (
    RuntimeServiceName.DECISION_CORE,
    RuntimeServiceName.GOVERNANCE_CHAIN,
    RuntimeServiceName.ACTION_EXECUTOR,
)
