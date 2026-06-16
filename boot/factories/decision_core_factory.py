from __future__ import annotations

from boot.registrations.register_decision_core import RuntimeDecisionExecutionService
from runtime.constructor_tokens import runtime_construction_token

CANON_BUILD_RUNTIME_DECISION_EXECUTION_SERVICE = True
CANON_BUILD_DECISION_CORE_COMPAT_WRAPPER = True
CANON_BUILD_DECISION_CORE_NAME_RESERVED_FOR_SOVEREIGN_ISSUER = True


def build_runtime_decision_execution_service(
    *,
    governance_chain: object,
    action_executor: object,
) -> RuntimeDecisionExecutionService:
    return RuntimeDecisionExecutionService(
        governance_chain=governance_chain,
        action_executor=action_executor,
        _construction_token=runtime_construction_token(),
    )


def build_decision_core(
    *,
    governance_chain: object,
    action_executor: object,
):
    return build_runtime_decision_execution_service(
        governance_chain=governance_chain,
        action_executor=action_executor,
    )


__all__ = [
    "CANON_BUILD_RUNTIME_DECISION_EXECUTION_SERVICE",
    "CANON_BUILD_DECISION_CORE_COMPAT_WRAPPER",
    "CANON_BUILD_DECISION_CORE_NAME_RESERVED_FOR_SOVEREIGN_ISSUER",
    "build_decision_core",
    "build_runtime_decision_execution_service",
]
