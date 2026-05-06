from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
CANON_CAPABILITY_ROUTING_REGISTRY = True
_ALLOWED_MATURITY = {'real', 'capability_shell', 'placeholder'}
def _normalize_text(value: object) -> str:
    return str(value or '').strip()
@dataclass(frozen=True)
class CapabilityRoute:
    route_key: str
    capability_key: str
    supported_action_types: tuple[str, ...] = ()
    maturity: str = 'real'
    enabled: bool = True
    base_cost: float = 0.0
    base_latency_ms: float = 0.0
    base_proofability: float = 0.0
    health_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        route_key = _normalize_text(self.route_key)
        capability_key = _normalize_text(self.capability_key)
        maturity = _normalize_text(self.maturity).lower() or 'real'
        if not route_key:
            raise ValueError('route_key must not be empty')
        if not capability_key:
            raise ValueError('capability_key must not be empty')
        if maturity not in _ALLOWED_MATURITY:
            raise ValueError(f'unsupported capability route maturity: {self.maturity}')
        action_types = tuple(
            _normalize_text(item).lower()
            for item in self.supported_action_types
            if _normalize_text(item)
        )
        object.__setattr__(self, 'route_key', route_key)
        object.__setattr__(self, 'capability_key', capability_key)
        object.__setattr__(self, 'maturity', maturity)
        object.__setattr__(self, 'supported_action_types', action_types)
        object.__setattr__(self, 'base_cost', max(0.0, float(self.base_cost)))
        object.__setattr__(self, 'base_latency_ms', max(0.0, float(self.base_latency_ms)))
        object.__setattr__(self, 'base_proofability', max(0.0, min(1.0, float(self.base_proofability))))
        object.__setattr__(self, 'health_score', max(0.0, min(1.0, float(self.health_score))))
    def supports_action_type(self, action_type: str) -> bool:
        if not self.supported_action_types:
            return True
        return _normalize_text(action_type).lower() in self.supported_action_types
class CapabilityRegistry:
    def __init__(self) -> None:
        self._routes: dict[str, CapabilityRoute] = {}
    def register(self, route: CapabilityRoute) -> None:
        route_key = _normalize_text(route.route_key)
        if not route_key:
            raise ValueError('route_key must not be empty')
        self._routes[route_key] = route
    def register_many(self, routes: list[CapabilityRoute] | tuple[CapabilityRoute, ...]) -> None:
        for route in routes:
            self.register(route)
    def get(self, route_key: str) -> CapabilityRoute | None:
        return self._routes.get(_normalize_text(route_key))
    def routes_for(self, *, capability_key: str, action_type: str) -> tuple[CapabilityRoute, ...]:
        normalized_capability = _normalize_text(capability_key)
        return tuple(
            route
            for route in self._routes.values()
            if route.capability_key == normalized_capability and route.supports_action_type(action_type)
        )
    def all_routes(self) -> tuple[CapabilityRoute, ...]:
        return tuple(self._routes.values())
