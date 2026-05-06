from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
CANON_ROUTE_EXPLAINER = True
@dataclass(frozen=True)
class RouteExplanation:
    selected_route_key: str | None
    summary: str
    factors: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return {
            'selected_route_key': self.selected_route_key,
            'summary': self.summary,
            'factors': dict(self.factors),
        }
