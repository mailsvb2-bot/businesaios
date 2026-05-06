from __future__ import annotations

"""Final owner for runtime boot guard.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells."""

CANON_RUNTIME_BOOT_GUARD_FINAL_OWNER = True
CANON_RUNTIME_BOOT_GUARD_NO_RUNTIME_ASSEMBLY = True

from canon.runtime_decision_path import CANONICAL_RUNTIME_DECISION_PATH
from runtime.errors import RuntimeConfigurationError
from runtime.registry import RuntimeRegistry
from runtime.runtime_policies import RuntimePolicies
from runtime.service_names import RuntimeServiceName
def validate_runtime_boot(registry: RuntimeRegistry) -> None:
    policies = RuntimePolicies()
    missing = [name for name in policies.required_services if not registry.has(name)]
    if missing:
        raise RuntimeConfigurationError(
            "Runtime boot is incomplete. Missing services: " + ", ".join(missing)
        )
    if registry.lifecycle.value != "registering":
        raise RuntimeConfigurationError(
            "Runtime boot guard must run before registry sealing."
        )
    _validate_decision_path(registry)
def _validate_decision_path(registry: RuntimeRegistry) -> None:
    decision_core = registry.get(RuntimeServiceName.DECISION_CORE)
    governance = registry.get(RuntimeServiceName.GOVERNANCE_CHAIN)
    executor = registry.get(RuntimeServiceName.ACTION_EXECUTOR)
    if decision_core is governance or decision_core is executor or governance is executor:
        raise RuntimeConfigurationError(
            "Decision core, governance chain, and action executor must be separate objects."
        )
    actual = (
        RuntimeServiceName.DECISION_CORE,
        *registry.dependencies_of(RuntimeServiceName.DECISION_CORE),
    )
    if tuple(actual) != CANONICAL_RUNTIME_DECISION_PATH:
        raise RuntimeConfigurationError(
            "Decision path is not canonical. "
            f"Expected {CANONICAL_RUNTIME_DECISION_PATH}, got {actual}."
        )
