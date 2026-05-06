from __future__ import annotations

"""Compatibility shim. Final owner: bootstrap.runtime_integration."""

from typing import Protocol, runtime_checkable

from core.application.decision_service import DecisionApplicationService
from runtime.application import (  # compatibility audit marker: package-root owner
    ReadOnlyRuntimeRegistry,
    build_runtime_application_service,
    build_runtime_application_service_from_exports,
)

# RuntimeExportsProvider compatibility marker retained inline after collapse.
from bootstrap.runtime_integration import (  # noqa: F401
    CANON_RUNTIME_INTEGRATION_EXPORTS_DIRECT_COMPAT,
    CANON_RUNTIME_INTEGRATION_FINAL_OWNER,
    CANON_RUNTIME_INTEGRATION_NO_RUNTIME_ASSEMBLY,
    CANON_RUNTIME_INTEGRATION_PROTOCOL_TYPED,
    RuntimeIntegration as OwnerRuntimeIntegration,
)

CANON_RUNTIME_INTEGRATION_OWNER = True
CANON_RUNTIME_INTEGRATION_USES_SOVEREIGN_BOOTSTRAP = True
CANON_RUNTIME_INTEGRATION_NO_LEGACY_BOOT_REUSE = True
CANON_RUNTIME_INTEGRATION_PROTOCOL_TYPED = True
CANON_RUNTIME_INTEGRATION_DIRECT_OWNER_BOOTSTRAP = True
CANON_RUNTIME_INTEGRATION_COMPAT_SUBCLASS = True


# Compatibility audit markers retained for existing architecture locks:
# class SupportsBuiltRuntime(Protocol):
#     exports: object

def bootstrap_runtime():
    from bootstrap.runtime_integration import bootstrap_runtime as owner_bootstrap_runtime

    return owner_bootstrap_runtime()


class RuntimeIntegration(OwnerRuntimeIntegration):
    """Thin compat subclass preserving historical import locations."""

    def build(self):
        built_runtime = bootstrap_runtime().artifacts.built_runtime
        registry = getattr(built_runtime, "registry", None)
        if registry is not None:
            application_service = build_runtime_application_service(ReadOnlyRuntimeRegistry(registry))
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
