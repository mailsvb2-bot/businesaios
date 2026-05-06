from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from observability.platform.telemetry.contracts import AppendOnlyTelemetryStore


class MetricEventStore(AppendOnlyTelemetryStore):
    """Canonical append-only store contract for platform metric events.

    This layer owns the event-backed metric emission primitive so sibling modules
    do not each redefine the same store protocol and emission semantics.
    """


@dataclass(frozen=True)
class Metrics:
    store: MetricEventStore

    def incr(
        self,
        *,
        tenant_id: str,
        name: str,
        value: int = 1,
        tags: Optional[dict[str, Any]] = None,
    ) -> None:
        self.store.append(
            tenant_id=tenant_id,
            user_id=None,
            event_type="metric_incr",
            payload={"name": name, "value": int(value), "tags": tags or {}},
        )

    def gauge(
        self,
        *,
        tenant_id: str,
        name: str,
        value: float,
        tags: Optional[dict[str, Any]] = None,
    ) -> None:
        self.store.append(
            tenant_id=tenant_id,
            user_id=None,
            event_type="metric_gauge",
            payload={"name": name, "value": float(value), "tags": tags or {}},
        )


__all__ = ["MetricEventStore", "Metrics"]
