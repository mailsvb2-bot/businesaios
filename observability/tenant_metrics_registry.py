from __future__ import annotations

"""Tenant-aware technical metrics registry.

CANON_COMPAT_SHIM = True

Observability only:
- stores metric samples
- computes passive snapshots
- no business routing
- no decision logic
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from observability.slo_contract import SLIKind


CANON_TENANT_METRICS_REGISTRY = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MetricAggregation(str, Enum):
    SUM = 'sum'
    LAST = 'last'
    AVG = 'avg'
    P50 = 'p50'
    P95 = 'p95'
    P99 = 'p99'
    RATE = 'rate'


@dataclass(frozen=True)
class MetricSample:
    tenant_id: str
    metric_name: str
    kind: SLIKind
    value: float
    aggregation: MetricAggregation
    emitted_at: datetime = field(default_factory=utc_now)
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.metric_name or '').strip():
            raise ValueError('metric_name is required')
        if self.emitted_at.tzinfo is None:
            raise ValueError('emitted_at must be timezone-aware')


class TenantMetricsRegistry:
    def __init__(self) -> None:
        self._samples: dict[tuple[str, str], list[MetricSample]] = {}

    def emit(self, *, tenant_id: str, metric_name: str, kind: SLIKind, value: float, aggregation: MetricAggregation, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        sample = MetricSample(
            tenant_id=require_tenant_id(tenant_id),
            metric_name=str(metric_name),
            kind=kind,
            value=float(value),
            aggregation=aggregation,
            emitted_at=emitted_at or utc_now(),
            labels={str(k): str(v) for k, v in dict(labels or {}).items()},
        )
        sample.validate()
        key = (sample.tenant_id, sample.metric_name)
        self._samples.setdefault(key, []).append(sample)

    def inc(self, *, tenant_id: str, metric_name: str, amount: float = 1.0, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.THROUGHPUT, value=float(amount), aggregation=MetricAggregation.SUM, labels=labels, emitted_at=emitted_at)

    def set_gauge(self, *, tenant_id: str, metric_name: str, value: float, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.GAUGE, value=float(value), aggregation=MetricAggregation.LAST, labels=labels, emitted_at=emitted_at)

    def observe_latency_ms(self, *, tenant_id: str, metric_name: str, value_ms: float, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.LATENCY_P95_MS, value=float(value_ms), aggregation=MetricAggregation.P95, labels=labels, emitted_at=emitted_at)

    def record_success_rate(self, *, tenant_id: str, metric_name: str, success_ratio: float, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.SUCCESS_RATE, value=float(success_ratio), aggregation=MetricAggregation.AVG, labels=labels, emitted_at=emitted_at)

    def record_error_rate(self, *, tenant_id: str, metric_name: str, error_ratio: float, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.ERROR_RATE, value=float(error_ratio), aggregation=MetricAggregation.AVG, labels=labels, emitted_at=emitted_at)

    def metric_snapshot(self, *, tenant_id: str, metric_name: str, window_seconds: int | None = None) -> dict[str, object] | None:
        tid = require_tenant_id(tenant_id)
        key = (tid, str(metric_name))
        samples = list(self._samples.get(key, []))
        if window_seconds is not None:
            cutoff = utc_now() - timedelta(seconds=max(1, int(window_seconds)))
            samples = [sample for sample in samples if sample.emitted_at >= cutoff]
        if not samples:
            return None
        latest = samples[-1]
        aggregated_value = self._aggregate(samples=samples, aggregation=latest.aggregation)
        merged_labels = self._merge_labels(samples)
        return {
            'tenant_id': tid,
            'metric_name': metric_name,
            'kind': latest.kind,
            'aggregation': latest.aggregation,
            'value': float(aggregated_value),
            'sample_count': len(samples),
            'labels': merged_labels,
            'window_seconds': window_seconds,
        }

    def snapshot(self, *, tenant_id: str, window_seconds: int | None = None) -> dict[str, dict[str, object]]:
        tid = require_tenant_id(tenant_id)
        names = sorted(name for (sample_tid, name) in self._samples.keys() if sample_tid == tid)
        result: dict[str, dict[str, object]] = {}
        for name in names:
            snap = self.metric_snapshot(tenant_id=tid, metric_name=name, window_seconds=window_seconds)
            if snap is not None:
                result[name] = snap
        return result

    @staticmethod
    def _aggregate(*, samples: list[MetricSample], aggregation: MetricAggregation) -> float:
        values = [float(item.value) for item in samples]
        if not values:
            return 0.0
        if aggregation is MetricAggregation.SUM:
            return float(sum(values))
        if aggregation is MetricAggregation.LAST:
            return float(values[-1])
        if aggregation is MetricAggregation.AVG:
            return float(sum(values) / len(values))
        if aggregation is MetricAggregation.P50:
            return TenantMetricsRegistry._percentile(values, 0.50)
        if aggregation is MetricAggregation.P95:
            return TenantMetricsRegistry._percentile(values, 0.95)
        if aggregation is MetricAggregation.P99:
            return TenantMetricsRegistry._percentile(values, 0.99)
        if aggregation is MetricAggregation.RATE:
            return float(sum(values))
        raise ValueError(f'unsupported aggregation: {aggregation}')

    @staticmethod
    def _percentile(values: list[float], p: float) -> float:
        ordered = sorted(float(v) for v in values)
        if len(ordered) == 1:
            return ordered[0]
        pos = (len(ordered) - 1) * max(0.0, min(1.0, p))
        lo = int(pos)
        hi = min(lo + 1, len(ordered) - 1)
        frac = pos - lo
        return ordered[lo] * (1.0 - frac) + ordered[hi] * frac

    @staticmethod
    def _merge_labels(samples: list[MetricSample]) -> dict[str, str]:
        merged: dict[str, str] = {}
        for sample in samples:
            merged.update({str(k): str(v) for k, v in sample.labels.items()})
        return merged


__all__ = [
    'CANON_TENANT_METRICS_REGISTRY',
    'MetricAggregation',
    'MetricSample',
    'TenantMetricsRegistry',
    'utc_now',
]
