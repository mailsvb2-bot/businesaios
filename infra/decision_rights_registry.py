from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DecisionRightsRegistry:
    _rights: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def register(self, action_name: str, allowed_scopes: tuple[str, ...]) -> None:
        self._rights[action_name] = tuple(allowed_scopes)

    def allowed_scopes_for(self, action_name: str) -> tuple[str, ...]:
        return self._rights.get(action_name, ())

    def is_allowed(self, *, action_name: str, actor_scope: str) -> bool:
        return actor_scope in set(self.allowed_scopes_for(action_name))

    def snapshot(self) -> dict[str, tuple[str, ...]]:
        return dict(self._rights)
