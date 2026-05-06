from __future__ import annotations

CANON_COMPAT_SHIM = True

from observability.slo_contract import SLIReading, SLOComparator, SLODefinition, SLOEvaluation
from observability.tenant_metrics_registry import TenantMetricsRegistry


CANON_SLI_COLLECTOR = True


class SLICollector:
    """Passive metrics -> SLI/SLO evidence adapter."""

    def __init__(self, *, metrics_registry: TenantMetricsRegistry) -> None:
        self._metrics_registry = metrics_registry

    def collect(self, *, tenant_id: str, sli_name: str, window_seconds: int | None = None) -> SLIReading | None:
        snapshot = self._metrics_registry.metric_snapshot(tenant_id=tenant_id, metric_name=sli_name, window_seconds=window_seconds)
        if snapshot is None:
            return None
        reading = SLIReading(
            tenant_id=tenant_id,
            sli_name=sli_name,
            sli_kind=snapshot['kind'],
            value=float(snapshot['value']),
            sample_count=int(snapshot['sample_count']),
            labels=dict(snapshot['labels']),
        )
        reading.validate()
        return reading

    def evaluate(self, slo: SLODefinition, *, window_seconds: int | None = None) -> SLOEvaluation | None:
        slo.validate()
        reading = self.collect(tenant_id=slo.tenant_id, sli_name=slo.sli_name, window_seconds=window_seconds)
        if reading is None:
            return None
        if reading.sample_count < slo.min_sample_count:
            return None
        is_compliant = self._compare(observed=float(reading.value), comparator=slo.comparator, target=float(slo.target_value))
        return SLOEvaluation(
            tenant_id=slo.tenant_id,
            slo_id=slo.slo_id,
            sli_name=slo.sli_name,
            observed_value=float(reading.value),
            target_value=float(slo.target_value),
            is_compliant=is_compliant,
            sample_count=int(reading.sample_count),
            labels={**dict(slo.labels), **dict(reading.labels)},
        )

    @staticmethod
    def _compare(*, observed: float, comparator: SLOComparator, target: float) -> bool:
        if comparator is SLOComparator.LTE:
            return observed <= target
        if comparator is SLOComparator.GTE:
            return observed >= target
        raise ValueError(f'unsupported SLO comparator: {comparator}')


__all__ = [
    'CANON_SLI_COLLECTOR',
    'SLICollector',
]
