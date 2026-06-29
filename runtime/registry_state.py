"""Canonical in-memory state for the runtime service registry.

Keeps mutable storage in one explicit place so ``runtime.registry`` can stay a
small owner surface for lifecycle + validation flow rather than an ad-hoc bag of
parallel dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.registry_snapshot import RuntimeRegistrySnapshot


@dataclass
class RuntimeRegistryState:
    services: dict[str, Any] = field(default_factory=dict)
    service_types: dict[str, str] = field(default_factory=dict)
    dependencies: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def has(self, name: str) -> bool:
        return name in self.services

    def get(self, name: str) -> Any:
        return self.services[name]

    def remember(self, *, name: str, service: Any, service_type: str, dependencies: tuple[str, ...]) -> None:
        self.services[name] = service
        self.service_types[name] = service_type
        self.dependencies[name] = dependencies

    def service_type_of(self, name: str) -> str:
        return self.service_types[name]

    def dependencies_of(self, name: str) -> tuple[str, ...]:
        return self.dependencies[name]

    def list_service_names(self) -> tuple[str, ...]:
        return tuple(self.services.keys())

    def snapshot(self) -> RuntimeRegistrySnapshot:
        return RuntimeRegistrySnapshot(
            service_names=self.list_service_names(),
            service_types=dict(self.service_types),
            dependencies=dict(self.dependencies),
        )


__all__ = ["RuntimeRegistryState"]
