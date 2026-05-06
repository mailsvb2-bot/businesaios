from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass

from observability.metrics import InMemoryMetrics
from observability.structured_logging import StructuredLogger


@dataclass(frozen=True)
class TelemetryBundle:
    logger: StructuredLogger
    metrics: InMemoryMetrics
