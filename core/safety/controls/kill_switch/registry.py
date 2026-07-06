from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .models import KillSwitchSnapshot


@dataclass
class InMemoryKillSwitchRegistry:
    switches: dict[str, KillSwitchSnapshot] = field(default_factory=dict)

    def upsert(self, snapshot: KillSwitchSnapshot) -> None:
        self.switches[str(snapshot.action_prefix)] = snapshot

    def matching(self, action: str) -> Iterable[KillSwitchSnapshot]:
        name = str(action or "")
        for prefix, snapshot in self.switches.items():
            if name.startswith(prefix):
                yield snapshot
