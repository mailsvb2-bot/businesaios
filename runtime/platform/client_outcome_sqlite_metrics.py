from __future__ import annotations

from datetime import datetime
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from observability.slo_contract import SLIKind
from observability.tenant_metrics_registry import MetricAggregation, MetricSample, TenantMetricsRegistry, utc_now
from runtime.platform.client_outcome_sqlite_core import _SQLiteOwner, _json_dumps, _json_loads


class SQLiteTenantMetricsRegistry:
    def __init__(self, *, owner: _SQLiteOwner) -> None:
        self._owner = owner

    def emit(
        self,
        *,
        tenant_id: str,
        metric_name: str,
        kind: SLIKind,
        value: float,
        aggregation: MetricAggregation,
        labels: Mapping[str, str] | None = None,
        emitted_at: datetime | None = None,
    ) -> None:
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
        with self._owner._lock, self._owner._connect() as conn:
            conn.execute(
                '''
                INSERT INTO client_outcome_metric_samples(
                    tenant_id, metric_name, kind, value, aggregation, emitted_at, labels_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    sample.tenant_id,
                    sample.metric_name,
                    sample.kind.value,
                    sample.value,
                    sample.aggregation.value,
                    sample.emitted_at.isoformat(),
                    _json_dumps(dict(sample.labels)),
                ),
            )
            conn.commit()

    def inc(self, *, tenant_id: str, metric_name: str, amount: float = 1.0, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.THROUGHPUT, value=amount, aggregation=MetricAggregation.SUM, labels=labels, emitted_at=emitted_at)

    def set_gauge(self, *, tenant_id: str, metric_name: str, value: float, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.GAUGE, value=value, aggregation=MetricAggregation.LAST, labels=labels, emitted_at=emitted_at)

    def observe_latency_ms(self, *, tenant_id: str, metric_name: str, value_ms: float, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.LATENCY_P95_MS, value=value_ms, aggregation=MetricAggregation.P95, labels=labels, emitted_at=emitted_at)

    def record_success_rate(self, *, tenant_id: str, metric_name: str, success_ratio: float, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.SUCCESS_RATE, value=success_ratio, aggregation=MetricAggregation.AVG, labels=labels, emitted_at=emitted_at)

    def record_error_rate(self, *, tenant_id: str, metric_name: str, error_ratio: float, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> None:
        self.emit(tenant_id=tenant_id, metric_name=metric_name, kind=SLIKind.ERROR_RATE, value=error_ratio, aggregation=MetricAggregation.AVG, labels=labels, emitted_at=emitted_at)

    def _samples(self, *, tenant_id: str, metric_name: str, window_seconds: int | None) -> list[MetricSample]:
        tid = require_tenant_id(tenant_id)
        with self._owner._lock, self._owner._connect() as conn:
            rows = conn.execute(
                '''
                SELECT kind, value, aggregation, emitted_at, labels_json
                FROM client_outcome_metric_samples
                WHERE tenant_id=? AND metric_name=?
                ORDER BY emitted_at, sample_id
                ''',
                (tid, str(metric_name)),
            ).fetchall()
        samples = [
            MetricSample(
                tenant_id=tid,
                metric_name=str(metric_name),
                kind=SLIKind(str(kind)),
                value=float(value),
                aggregation=MetricAggregation(str(aggregation)),
                emitted_at=datetime.fromisoformat(str(emitted_at)),
                labels=dict(_json_loads(str(labels_json))),
            )
            for kind, value, aggregation, emitted_at, labels_json in rows
        ]
        if window_seconds is not None:
            cutoff = utc_now().timestamp() - max(1, int(window_seconds))
            samples = [sample for sample in samples if sample.emitted_at.timestamp() >= cutoff]
        return samples

    def metric_snapshot(self, *, tenant_id: str, metric_name: str, window_seconds: int | None = None) -> dict[str, object] | None:
        samples = self._samples(tenant_id=tenant_id, metric_name=metric_name, window_seconds=window_seconds)
        if not samples:
            return None
        latest = samples[-1]
        return {
            'tenant_id': require_tenant_id(tenant_id),
            'metric_name': metric_name,
            'kind': latest.kind,
            'aggregation': latest.aggregation,
            'value': float(TenantMetricsRegistry._aggregate(samples=samples, aggregation=latest.aggregation)),
            'sample_count': len(samples),
            'labels': TenantMetricsRegistry._merge_labels(samples),
            'window_seconds': window_seconds,
        }

    def snapshot(self, *, tenant_id: str, window_seconds: int | None = None) -> dict[str, dict[str, object]]:
        tid = require_tenant_id(tenant_id)
        with self._owner._lock, self._owner._connect() as conn:
            rows = conn.execute(
                'SELECT DISTINCT metric_name FROM client_outcome_metric_samples WHERE tenant_id=? ORDER BY metric_name',
                (tid,),
            ).fetchall()
        result: dict[str, dict[str, object]] = {}
        for (name,) in rows:
            value = self.metric_snapshot(tenant_id=tid, metric_name=str(name), window_seconds=window_seconds)
            if value is not None:
                result[str(name)] = value
        return result


__all__ = ['SQLiteTenantMetricsRegistry']
