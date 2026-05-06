from __future__ import annotations

from dataclasses import dataclass, field

from runtime.constructor_tokens import is_valid_runtime_construction_token
from runtime.registry import RuntimeRegistry
from runtime.sealed_types import SealedType
from runtime.service_names import RuntimeServiceName
from boot.registrations._shared import register_runtime_service
from boot.runtime_dependency_sets import DECISION_CORE_DEPS
from runtime.service_types import RuntimeServiceType

CANON_RUNTIME_DECISION_EXECUTION_SERVICE = True
CANON_RUNTIME_DECISION_EXECUTION_SERVICE_OWNS_GOVERNED_EXECUTION = True
CANON_RUNTIME_DECISION_CORE_NAME_RESERVED_FOR_SOVEREIGN_ISSUER = True
CANON_RUNTIME_DECISION_CORE_COMPAT_ALIAS = True
CANON_REGISTER_RUNTIME_DECISION_EXECUTION_SERVICE = True
CANON_REGISTER_DECISION_CORE_COMPAT_WRAPPER = True


@dataclass
class RuntimeDecisionExecutionService(SealedType):
    """Runtime-owned governed action execution service.

    This object is *not* the sovereign ``core.ai.decision_core.DecisionCore``.
    Its ownership is limited to runtime governance + execution on the canonical
    boot path.
    """

    governance_chain: object
    action_executor: object
    _construction_token: object = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_runtime_construction_token(self._construction_token):
            raise RuntimeError(
                "Illegal runtime decision execution service construction. Use canonical boot factory path."
            )

    def decide_and_execute(self, action: object) -> dict:
        allowed = self.governance_chain.evaluate(action)
        if not allowed:
            return {
                "status": "blocked",
                "reason": "governance_rejected",
                "action_type": type(action).__name__,
            }
        return self.action_executor.execute(action)


# Transitional ABI only. Keep the historical symbol importable while reserving
# the semantic term ``DecisionCore`` for the sovereign issuer.
RuntimeDecisionCore = RuntimeDecisionExecutionService


def register_runtime_decision_execution_service(registry: RuntimeRegistry):
    from boot.factories import build_runtime_decision_execution_service

    service = build_runtime_decision_execution_service(
        governance_chain=registry.get(RuntimeServiceName.GOVERNANCE_CHAIN),
        action_executor=registry.get(RuntimeServiceName.ACTION_EXECUTOR),
    )

    return register_runtime_service(
        registry,
        name=RuntimeServiceName.DECISION_CORE,
        service=service,
        service_type=RuntimeServiceType.CORE,
        dependencies=DECISION_CORE_DEPS,
    )


__all__ = [
    "CANON_REGISTER_DECISION_CORE_COMPAT_WRAPPER",
    "CANON_REGISTER_RUNTIME_DECISION_EXECUTION_SERVICE",
    "CANON_RUNTIME_DECISION_CORE_COMPAT_ALIAS",
    "CANON_RUNTIME_DECISION_CORE_NAME_RESERVED_FOR_SOVEREIGN_ISSUER",
    "CANON_RUNTIME_DECISION_EXECUTION_SERVICE",
    "CANON_RUNTIME_DECISION_EXECUTION_SERVICE_OWNS_GOVERNED_EXECUTION",
    "RuntimeDecisionCore",
    "RuntimeDecisionExecutionService",
    "register_decision_core",
    "register_runtime_decision_execution_service",
]


def register_decision_core(registry: RuntimeRegistry):
    return register_runtime_decision_execution_service(registry)
