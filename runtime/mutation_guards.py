from __future__ import annotations

from runtime.lifecycle import RuntimeLifecycle
from runtime.registry import RuntimeRegistry


def assert_registry_is_mutable(registry: RuntimeRegistry) -> None:
    if registry.lifecycle != RuntimeLifecycle.REGISTERING:
        raise RuntimeError(
            f"Runtime registry is not mutable in state '{registry.lifecycle.value}'."
        )


def assert_registry_is_sealed(registry: RuntimeRegistry) -> None:
    if registry.lifecycle != RuntimeLifecycle.SEALED:
        raise RuntimeError(
            f"Runtime registry must be sealed, got '{registry.lifecycle.value}'."
        )
