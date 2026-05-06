from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InMemoryFeatureFlagStore:
    _flags: dict[str, bool] = field(default_factory=dict)

    def get(self, name: str, default: bool = False) -> bool:
        return self._flags.get(name, default)

    def set(self, name: str, value: bool) -> None:
        self._flags[name] = value

    def snapshot(self) -> dict[str, bool]:
        return dict(self._flags)
