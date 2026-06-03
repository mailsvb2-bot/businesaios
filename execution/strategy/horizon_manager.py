from __future__ import annotations
from typing import Any
from collections.abc import Mapping
CANON_HORIZON_MANAGER = True
class HorizonManager:
    _VALID = {'today', 'week', 'month', 'quarter'}
    def resolve(self, *, goal: str, metadata: Mapping[str, Any] | None = None) -> str:
        payload = dict(metadata or {})
        explicit = str(payload.get('planning_horizon') or payload.get('horizon') or '').strip().lower()
        if explicit in self._VALID:
            return explicit
        text = str(goal or '').lower()
        if any(token in text for token in ('today', 'now', 'urgent', 'immediately')):
            return 'today'
        if any(token in text for token in ('quarter', 'roadmap', 'portfolio')):
            return 'quarter'
        if any(token in text for token in ('month', 'monthly', 'retention', 'brand')):
            return 'month'
        return 'week'
