from __future__ import annotations

from runtime.errors import (
    RuntimeDuplicateServiceError,
    RuntimeIllegalServiceTypeError,
    RuntimeMissingDependencyError,
    RuntimeMissingServiceError,
    RuntimeRegistrySealedError,
)
from runtime.lifecycle import RuntimeLifecycle
from runtime.registry_state import RuntimeRegistryState
from runtime.runtime_policies import RuntimePolicies


def _resolve_registry_state(
    *,
    registry_state: RuntimeRegistryState | None = None,
    state: RuntimeRegistryState | None = None,
) -> RuntimeRegistryState:
    resolved = registry_state if registry_state is not None else state
    if resolved is None:
        raise TypeError("registry_state is required")
    return resolved


def ensure_can_begin_registration(*, lifecycle: RuntimeLifecycle) -> None:
    if lifecycle != RuntimeLifecycle.CREATED:
        raise RuntimeRegistrySealedError(
            f"Cannot begin registration from state '{lifecycle.value}'."
        )


def ensure_can_register(
    *,
    lifecycle: RuntimeLifecycle,
    registry_state: RuntimeRegistryState | None = None,
    state: RuntimeRegistryState | None = None,
    policies: RuntimePolicies,
    name: str,
    service_type: str,
    dependencies: tuple[str, ...],
) -> None:
    resolved_state = _resolve_registry_state(registry_state=registry_state, state=state)
    if lifecycle != RuntimeLifecycle.REGISTERING:
        raise RuntimeRegistrySealedError(
            f"Service '{name}' cannot be registered in state '{lifecycle.value}'."
        )
    if resolved_state.has(name):
        raise RuntimeDuplicateServiceError(
            f"Runtime service '{name}' is already registered."
        )
    if service_type not in policies.allowed_service_types:
        raise RuntimeIllegalServiceTypeError(
            f"Illegal runtime service type '{service_type}' for service '{name}'."
        )
    for dependency in dependencies:
        if not resolved_state.has(dependency):
            raise RuntimeMissingDependencyError(
                f"Service '{name}' requires missing dependency '{dependency}'."
            )


def ensure_registered(
    *,
    registry_state: RuntimeRegistryState | None = None,
    state: RuntimeRegistryState | None = None,
    name: str,
) -> None:
    resolved_state = _resolve_registry_state(registry_state=registry_state, state=state)
    if not resolved_state.has(name):
        raise RuntimeMissingServiceError(f"Runtime service '{name}' is not registered.")


def ensure_can_seal(
    *,
    lifecycle: RuntimeLifecycle,
    registry_state: RuntimeRegistryState | None = None,
    state: RuntimeRegistryState | None = None,
    policies: RuntimePolicies,
) -> None:
    resolved_state = _resolve_registry_state(registry_state=registry_state, state=state)
    if lifecycle != RuntimeLifecycle.REGISTERING:
        raise RuntimeRegistrySealedError(
            f"Cannot seal registry from state '{lifecycle.value}'."
        )
    missing_required = [
        service_name
        for service_name in policies.required_services
        if not resolved_state.has(service_name)
    ]
    if missing_required:
        raise RuntimeMissingServiceError(
            "Runtime registry cannot be sealed; missing required services: "
            + ", ".join(missing_required)
        )
