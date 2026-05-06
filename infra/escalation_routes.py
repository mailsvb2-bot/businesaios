from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EscalationRoute:
    action_name: str
    route: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class EscalationRoutesRegistry:
    _routes: dict[str, EscalationRoute] = field(default_factory=dict)

    def register(self, route: EscalationRoute) -> None:
        self._routes[route.action_name] = route

    def get(self, action_name: str) -> EscalationRoute | None:
        return self._routes.get(action_name)

    def snapshot(self) -> dict[str, tuple[str, ...]]:
        return {
            name: route.route
            for name, route in self._routes.items()
        }
