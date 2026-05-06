from __future__ import annotations

"""Delivery observability metrics for outbox-backed transports.

CANON_COMPAT_SHIM = True

Infra-only telemetry helpers.
No routing or business decision logic is allowed here.
"""

from dataclasses import dataclass, field
from typing import Mapping

from observability.metrics import InMemoryMetrics


CANON_DELIVERY_OBSERVABILITY_METRICS = True


def _labels(*, transport_name: str, backend_name: str | None = None, topic: str | None = None, final_state: str | None = None) -> dict[str, str]:
    labels = {"transport": str(transport_name or "unknown")}
    if backend_name:
        labels["backend"] = str(backend_name)
    if topic:
        labels["topic"] = str(topic)
    if final_state:
        labels["final_state"] = str(final_state)
    return labels


@dataclass
class DeliveryObservabilityMetrics:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)
    metric_prefix: str = "delivery"

    def record_worker_healthcheck(self, *, tenant_id: str, transport_name: str, backend_name: str, healthy: bool) -> None:
        labels = _labels(transport_name=transport_name, backend_name=backend_name)
        self.metrics.inc(f"{self.metric_prefix}.worker.healthcheck.total", tenant_id=tenant_id, labels=labels)
        self.metrics.set_gauge(
            f"{self.metric_prefix}.worker.backend_healthy",
            1.0 if healthy else 0.0,
            tenant_id=tenant_id,
            labels=labels,
        )

    def record_claimed(self, *, tenant_id: str, transport_name: str, backend_name: str, topic: str) -> None:
        self.metrics.inc(
            f"{self.metric_prefix}.claimed.total",
            tenant_id=tenant_id,
            labels=_labels(transport_name=transport_name, backend_name=backend_name, topic=topic),
        )

    def record_delivered(self, *, tenant_id: str, transport_name: str, backend_name: str, topic: str, attempts_after: int) -> None:
        labels = _labels(transport_name=transport_name, backend_name=backend_name, topic=topic, final_state="delivered")
        self.metrics.inc(f"{self.metric_prefix}.delivered.total", tenant_id=tenant_id, labels=labels)
        self.metrics.observe(f"{self.metric_prefix}.attempts_before_delivery", float(attempts_after), tenant_id=tenant_id, labels=labels)

    def record_retry(self, *, tenant_id: str, transport_name: str, backend_name: str, topic: str, error_family: str) -> None:
        labels = _labels(transport_name=transport_name, backend_name=backend_name, topic=topic, final_state="pending")
        labels["error_family"] = str(error_family or "unknown")
        self.metrics.inc(f"{self.metric_prefix}.retry.total", tenant_id=tenant_id, labels=labels)

    def record_dead_letter(self, *, tenant_id: str, transport_name: str, backend_name: str, topic: str, error_family: str) -> None:
        labels = _labels(transport_name=transport_name, backend_name=backend_name, topic=topic, final_state="dead")
        labels["error_family"] = str(error_family or "unknown")
        self.metrics.inc(f"{self.metric_prefix}.dead_letter.total", tenant_id=tenant_id, labels=labels)

    def record_skipped(self, *, tenant_id: str, transport_name: str, backend_name: str, reason: str) -> None:
        labels = _labels(transport_name=transport_name, backend_name=backend_name)
        labels["reason"] = str(reason or "unknown")
        self.metrics.inc(f"{self.metric_prefix}.skipped.total", tenant_id=tenant_id, labels=labels)

    def record_batch(self, *, tenant_id: str, transport_name: str, backend_name: str, processed: int, delivered: int, retried: int, dead_lettered: int, skipped: int) -> None:
        labels = _labels(transport_name=transport_name, backend_name=backend_name)
        self.metrics.observe(f"{self.metric_prefix}.batch.processed", float(processed), tenant_id=tenant_id, labels=labels)
        self.metrics.observe(f"{self.metric_prefix}.batch.delivered", float(delivered), tenant_id=tenant_id, labels=labels)
        self.metrics.observe(f"{self.metric_prefix}.batch.retried", float(retried), tenant_id=tenant_id, labels=labels)
        self.metrics.observe(f"{self.metric_prefix}.batch.dead_lettered", float(dead_lettered), tenant_id=tenant_id, labels=labels)
        self.metrics.observe(f"{self.metric_prefix}.batch.skipped", float(skipped), tenant_id=tenant_id, labels=labels)

    def snapshot(self) -> dict:
        return self.metrics.snapshot()

    def tenant_snapshot(self, *, tenant_id: str, window_seconds: int | None = None) -> dict[str, dict[str, object]]:
        return self.metrics.tenant_snapshot(tenant_id=tenant_id, window_seconds=window_seconds)


__all__ = [
    "CANON_DELIVERY_OBSERVABILITY_METRICS",
    "DeliveryObservabilityMetrics",
]
