from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ForbiddenOperatorActions:
    actions: tuple[str, ...] = field(default_factory=tuple)

    def contains(self, action_name: str) -> bool:
        return action_name in set(self.actions)
