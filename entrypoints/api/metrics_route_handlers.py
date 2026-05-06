from __future__ import annotations

"""Final owner: entrypoints.api.metrics_route_handlers."""

CANON_API_METRICS_ROUTE_HANDLERS_FINAL_OWNER = True

from dataclasses import dataclass, field
from typing import Any

from observability.metrics import InMemoryMetrics


CANON_API_METRICS_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class MetricsRouteHandlers:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)

    def global_snapshot(self) -> dict[str, Any]:
        return self.metrics.snapshot()

    def tenant_snapshot(self, *, tenant_id: str, window_seconds: int | None = None) -> dict[str, Any]:
        normalized_window = None if window_seconds is None else max(1, int(window_seconds))
        return {
            'tenant_id': tenant_id,
            'window_seconds': normalized_window,
            'metrics': self.metrics.tenant_snapshot(tenant_id=tenant_id, window_seconds=normalized_window),
        }


__all__ = [
    'CANON_API_METRICS_ROUTE_HANDLERS',
    'MetricsRouteHandlers',
]
