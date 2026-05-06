from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeRegistrySnapshot:
    service_names: tuple[str, ...]
    service_types: dict[str, str]
    dependencies: dict[str, tuple[str, ...]]
