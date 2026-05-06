from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KillSwitchRegistry:
    _switches: dict[str, bool] = field(default_factory=dict)

    def is_tripped(self, name: str) -> bool:
        return self._switches.get(name, False)

    def trip(self, name: str) -> None:
        self._switches[name] = True

    def reset(self, name: str) -> None:
        self._switches[name] = False

    def snapshot(self) -> dict[str, bool]:
        return dict(self._switches)
