from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.analytics.business_scorecard import BusinessAnalyticsService


@dataclass
class ApplicationBusinessAnalyticsService:
    event_store: Any
    _service: BusinessAnalyticsService = field(default_factory=BusinessAnalyticsService)

    def build_scorecard(self, *, tenant_id: str, window_days: int = 30, now_ms: int | None = None):
        if self.event_store is None or not hasattr(self.event_store, 'iter_events'):
            raise ValueError('event_store must provide iter_events(...)')
        if not 1 <= (days := int(window_days)) <= 3650:
            raise ValueError('window_days must be between 1 and 3650')
        end_ms = int(now_ms) if now_ms is not None else int(time.time() * 1000)
        start_ms = max(0, end_ms - days * 24 * 3600 * 1000)
        events = list(self.event_store.iter_events(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms))
        return self._service.build_scorecard(tenant_id=str(tenant_id), events=events, window_days=days, generated_at_ms=end_ms)
