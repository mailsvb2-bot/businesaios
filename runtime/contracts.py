from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RuntimeService(Protocol):
    """Marker protocol for runtime services."""


@runtime_checkable
class RuntimeRegistrable(Protocol):
    def register(self, registry: "RuntimeRegistry") -> "RegistrationResult":
        ...
