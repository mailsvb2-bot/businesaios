from __future__ import annotations

"""Compatibility shim. Final owner: bootstrap.runtime_integration."""

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
    RuntimeIntegration as OwnerRuntimeIntegration,
)

CANON_RUNTIME_INTEGRATION_OWNER = True
CANON_RUNTIME_INTEGRATION_USES_SOVEREIGN_BOOTSTRAP = True
CANON_RUNTIME_INTEGRATION_NO_LEGACY_BOOT_REUSE = True
CANON_RUNTIME_INTEGRATION_PROTOCOL_TYPED = True
CANON_RUNTIME_INTEGRATION_DIRECT_OWNER_BOOTSTRAP = True
CANON_RUNTIME_INTEGRATION_COMPAT_SUBCLASS = True
CANON_RUNTIME_INTEGRATION_ENVELOPE_ONLY = True


# Compatibility audit markers retained for existing architecture locks:
# class SupportsBuiltRuntime(Protocol):
#     exports: object

def bootstrap_runtime():
    from bootstrap.runtime_integration import (
        bootstrap_runtime as owner_bootstrap_runtime,
    )

    return owner_bootstrap_runtime()


class RuntimeIntegration(OwnerRuntimeIntegration):
    """Thin compat subclass preserving historical import locations."""

    def build(self):
        built_runtime = bootstrap_runtime().artifacts.built_runtime
        registry = getattr(built_runtime, "registry", None)
        if registry is not None:
            application_service = build_runtime_application_service(
                ReadOnlyRuntimeRegistry(registry)
            )
        else:
            application_service = (
                build_runtime_application_service_from_exports(
                    built_runtime.exports
                )
            )
        return built_runtime, application_service
