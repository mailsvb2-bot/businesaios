from __future__ import annotations

from boot.registrations._shared import register_runtime_service
from boot.runtime_dependency_sets import DECISION_CORE_DEPS
from boot.runtime_service_contracts import RuntimeDecisionExecutionService
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType

CANON_RUNTIME_DECISION_EXECUTION_SERVICE = True
CANON_RUNTIME_DECISION_EXECUTION_SERVICE_OWNS_GOVERNED_EXECUTION = True
CANON_RUNTIME_DECISION_CORE_NAME_RESERVED_FOR_SOVEREIGN_ISSUER = True
CANON_REGISTER_RUNTIME_DECISION_EXECUTION_SERVICE = True
CANON_REGISTER_DECISION_CORE_COMPAT_WRAPPER = True
CANON_REGISTER_DECISION_CORE_NO_EXECUTABLE_ALIAS_EXPORT = True


def register_runtime_decision_execution_service(registry: RuntimeRegistry):
    from boot.factories.decision_core_factory import build_runtime_decision_execution_service

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


def register_decision_core(registry: RuntimeRegistry):
    return register_runtime_decision_execution_service(registry)


__all__ = [
    "CANON_REGISTER_DECISION_CORE_COMPAT_WRAPPER",
    "CANON_REGISTER_DECISION_CORE_NO_EXECUTABLE_ALIAS_EXPORT",
    "CANON_REGISTER_RUNTIME_DECISION_EXECUTION_SERVICE",
    "CANON_RUNTIME_DECISION_CORE_NAME_RESERVED_FOR_SOVEREIGN_ISSUER",
    "CANON_RUNTIME_DECISION_EXECUTION_SERVICE",
    "CANON_RUNTIME_DECISION_EXECUTION_SERVICE_OWNS_GOVERNED_EXECUTION",
    "RuntimeDecisionExecutionService",
    "register_decision_core",
    "register_runtime_decision_execution_service",
]
