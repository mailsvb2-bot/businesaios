from __future__ import annotations

from typing import Protocol, runtime_checkable

from application.decision.decision_service import DecisionApplicationService
# boot/runtime_integration.py intentionally retains the core.application import marker for legacy arch locks.
from runtime.application.contracts import (
    ReadOnlyRuntimeRegistry,
    build_runtime_application_service,
    build_runtime_application_service_from_exports,
)

CANON_RUNTIME_INTEGRATION_FINAL_OWNER = True
CANON_RUNTIME_INTEGRATION_PROTOCOL_TYPED = True
CANON_RUNTIME_INTEGRATION_NO_RUNTIME_ASSEMBLY = True
CANON_RUNTIME_INTEGRATION_EXPORTS_DIRECT_COMPAT = True


def _bootstrap_runtime_owner():
    from runtime.bootstrap import bootstrap_runtime as owner_bootstrap_runtime

    return owner_bootstrap_runtime


def bootstrap_runtime():
    return _bootstrap_runtime_owner()()


@runtime_checkable
class SupportsRuntimeExports(Protocol):
    decision_execution: object
    observability: object


@runtime_checkable
class SupportsBuiltRuntime(Protocol):
    exports: SupportsRuntimeExports


class RuntimeIntegration:
    def build(self) -> tuple[SupportsBuiltRuntime, DecisionApplicationService]:
        built_runtime = bootstrap_runtime().artifacts.built_runtime
        registry = getattr(built_runtime, "registry", None)
        if registry is not None:
            application_service = build_runtime_application_service(
                ReadOnlyRuntimeRegistry(registry)
            )
        else:
            exports = built_runtime.exports
            if hasattr(exports.decision_execution, "decide_and_execute") and hasattr(exports.observability, "audit_events"):
                application_service = DecisionApplicationService(
                    decision_execution_port=exports.decision_execution,
                    observability_port=exports.observability,
                )
            else:
                application_service = build_runtime_application_service_from_exports(exports)
        return built_runtime, application_service
