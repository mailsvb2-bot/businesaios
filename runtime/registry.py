from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.lifecycle import RuntimeLifecycle
from runtime.registry_state import RuntimeRegistryState
from runtime.registry_validators import (
    ensure_can_begin_registration,
    ensure_can_register,
    ensure_can_seal,
    ensure_registered,
)
from runtime.runtime_policies import RuntimePolicies

CANON_RUNTIME_REGISTRY_OWNER = True


@dataclass
class RuntimeRegistry:
    _state: RuntimeRegistryState = field(default_factory=RuntimeRegistryState)
    _lifecycle: RuntimeLifecycle = RuntimeLifecycle.CREATED
    _policies: RuntimePolicies = field(default_factory=RuntimePolicies)

    @property
    def lifecycle(self) -> RuntimeLifecycle:
        return self._lifecycle

    def begin_registration(self) -> None:
        ensure_can_begin_registration(lifecycle=self._lifecycle)
        self._lifecycle = RuntimeLifecycle.REGISTERING

    def register(
        self,
        *,
        name: str,
        service: Any,
        service_type: str,
        dependencies: tuple[str, ...] = (),
    ) -> None:
        ensure_can_register(
            lifecycle=self._lifecycle,
            state=self._state,
            policies=self._policies,
            name=name,
            service_type=service_type,
            dependencies=dependencies,
        )
        self._state.remember(
            name=name,
            service=service,
            service_type=service_type,
            dependencies=dependencies,
        )

    def get(self, name: str) -> Any:
        ensure_registered(state=self._state, name=name)
        return self._state.get(name)

    def has(self, name: str) -> bool:
        return self._state.has(name)

    def service_type_of(self, name: str) -> str:
        ensure_registered(state=self._state, name=name)
        return self._state.service_type_of(name)

    def dependencies_of(self, name: str) -> tuple[str, ...]:
        ensure_registered(state=self._state, name=name)
        return self._state.dependencies_of(name)

    def list_service_names(self) -> tuple[str, ...]:
        return self._state.list_service_names()

    def seal(self) -> None:
        ensure_can_seal(
            lifecycle=self._lifecycle,
            state=self._state,
            policies=self._policies,
        )
        self._lifecycle = RuntimeLifecycle.SEALED

    def snapshot(self):
        return self._state.snapshot()


__all__ = ["CANON_RUNTIME_REGISTRY_OWNER", "RuntimeRegistry"]
