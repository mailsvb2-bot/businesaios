from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

from observability.tenant_metrics_registry import TenantMetricsRegistry
from runtime.business_autonomy.provider_probe_observability_payload import (
    build_live_probe_gauge_payload,
    build_live_probe_labels,
)
from runtime.business_autonomy.provider_webhook_inbound_observability_payload import (
    build_webhook_inbound_handoff_labels,
    build_webhook_inbound_handoff_rate_labels,
)

CANON_PROVIDER_RUNTIME_OBSERVABILITY = True


@dataclass(frozen=True)
class ProviderRuntimeObservability:
    metrics_registry: TenantMetricsRegistry = field(default_factory=TenantMetricsRegistry)

    def record_sync(self, *, tenant_id: str, provider_key: str, operation: str, status: str, accepted: bool, mode: str) -> None:
        labels = {'provider_key': provider_key, 'operation': operation, 'mode': mode, 'status': status}
        self.metrics_registry.inc(tenant_id=tenant_id, metric_name='provider_runtime.sync_total', amount=1.0, labels=labels)
        self.metrics_registry.record_success_rate(tenant_id=tenant_id, metric_name='provider_runtime.sync_success_rate', success_ratio=1.0 if accepted else 0.0, labels={'provider_key': provider_key, 'mode': mode})

    def record_webhook(self, *, tenant_id: str, provider_key: str, status: str, accepted: bool, topic: str) -> None:
        labels = {'provider_key': provider_key, 'status': status, 'topic': topic}
        self.metrics_registry.inc(tenant_id=tenant_id, metric_name='provider_runtime.webhook_total', amount=1.0, labels=labels)
        self.metrics_registry.record_success_rate(tenant_id=tenant_id, metric_name='provider_runtime.webhook_accept_rate', success_ratio=1.0 if accepted else 0.0, labels={'provider_key': provider_key, 'topic': topic})


    def record_webhook_inbound_handoff(self, *, tenant_id: str, provider_key: str, status: str, inbound_summary: Mapping[str, object] | None = None) -> None:
        labels = build_webhook_inbound_handoff_labels(
            provider_key=provider_key,
            status=status,
            inbound_summary=inbound_summary,
        )
        self.metrics_registry.inc(tenant_id=tenant_id, metric_name='provider_runtime.webhook_inbound_handoff_total', amount=1.0, labels=labels)
        self.metrics_registry.record_success_rate(
            tenant_id=tenant_id,
            metric_name='provider_runtime.webhook_inbound_handoff_accept_rate',
            success_ratio=1.0 if bool(dict(inbound_summary or {}).get('accepted')) else 0.0,
            labels=build_webhook_inbound_handoff_rate_labels(provider_key=provider_key, inbound_summary=inbound_summary),
        )
    def record_live_probe(self, *, tenant_id: str, provider_key: str, status: str, ok: bool, mode: str, metadata: Mapping[str, object] | None = None) -> None:
        labels = build_live_probe_labels(
            provider_key=provider_key,
            status=status,
            mode=mode,
            metadata=metadata,
        )
        self.metrics_registry.inc(tenant_id=tenant_id, metric_name='provider_runtime.live_probe_total', amount=1.0, labels=labels)
        self.metrics_registry.record_success_rate(tenant_id=tenant_id, metric_name='provider_runtime.live_probe_success_rate', success_ratio=1.0 if ok else 0.0, labels={'provider_key': provider_key, 'mode': mode})
        gauge = build_live_probe_gauge_payload(metadata=metadata)
        if gauge is not None:
            metric_name, value = gauge
            self.metrics_registry.set_gauge(tenant_id=tenant_id, metric_name=metric_name, value=float(value), labels=labels)


__all__ = ['CANON_PROVIDER_RUNTIME_OBSERVABILITY', 'ProviderRuntimeObservability']
