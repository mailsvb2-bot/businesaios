from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field
from typing import Mapping

from observability.slo_contract import SLIKind
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry


CANON_INMEMORY_METRICS = True


@dataclass
class InMemoryMetrics:
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    tenant_registry: TenantMetricsRegistry = field(default_factory=TenantMetricsRegistry)

    def inc(self, name: str, value: int = 1, *, tenant_id: str | None = None, labels: Mapping[str, str] | None = None) -> None:
        self.counters[name] = self.counters.get(name, 0) + int(value)
        if tenant_id is not None:
            self.tenant_registry.emit(
                tenant_id=str(tenant_id),
                metric_name=str(name),
                kind=SLIKind.THROUGHPUT,
                value=float(value),
                aggregation=MetricAggregation.SUM,
                labels=labels,
            )

    def set_gauge(self, name: str, value: float, *, tenant_id: str | None = None, labels: Mapping[str, str] | None = None) -> None:
        self.gauges[name] = float(value)
        if tenant_id is not None:
            self.tenant_registry.emit(
                tenant_id=str(tenant_id),
                metric_name=str(name),
                kind=SLIKind.GAUGE,
                value=float(value),
                aggregation=MetricAggregation.LAST,
                labels=labels,
            )

    def observe(self, name: str, value: float, *, tenant_id: str | None = None, labels: Mapping[str, str] | None = None) -> None:
        if tenant_id is not None:
            self.tenant_registry.emit(
                tenant_id=str(tenant_id),
                metric_name=str(name),
                kind=SLIKind.LATENCY_P95_MS,
                value=float(value),
                aggregation=MetricAggregation.P95,
                labels=labels,
            )

    def snapshot(self) -> dict:
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
        }

    def tenant_snapshot(self, *, tenant_id: str, window_seconds: int | None = None) -> dict[str, dict[str, object]]:
        return self.tenant_registry.snapshot(tenant_id=tenant_id, window_seconds=window_seconds)


@dataclass
class CounterStore:
    """Small additive compatibility layer for newer runtime patches.

    Keeps the original InMemoryMetrics surface intact while providing the
    lighter counter-only API expected by merged runtime modules.
    """

    counters: dict[str, float] = field(default_factory=dict)

    def inc(self, name: str, amount: float = 1.0) -> None:
        if amount < 0:
            raise ValueError("counter increments must be non-negative")
        self.counters[name] = self.counters.get(name, 0.0) + float(amount)

    def set(self, name: str, value: float) -> None:
        self.counters[name] = float(value)

    def get(self, name: str) -> float:
        return float(self.counters.get(name, 0.0))

    def snapshot(self) -> dict[str, float]:
        return dict(self.counters)
