from __future__ import annotations

from dataclasses import dataclass

from infra.feature_flag_store import InMemoryFeatureFlagStore


@dataclass(frozen=True)
class FeatureFlags:
    store: InMemoryFeatureFlagStore

    def is_enabled(self, name: str, *, default: bool = False) -> bool:
        return self.store.get(name, default=default)

    def enable(self, name: str) -> None:
        self.store.set(name, True)

    def disable(self, name: str) -> None:
        self.store.set(name, False)
