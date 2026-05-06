from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass

from observability.metrics import InMemoryMetrics


@dataclass(frozen=True)
class MetricsExporter:
    metrics: InMemoryMetrics

    def export(self) -> dict:
        return self.metrics.snapshot()
