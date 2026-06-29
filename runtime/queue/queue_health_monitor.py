"""Operational monitor for queue health sampling.

This monitor reads queue health, routes derived alerts, persists rollups, and
can optionally attach a read-only backpressure/fairness sample. It does not
mutate queue execution state and must never become a second brain.
"""

from __future__ import annotations


from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable

from core.tenancy.normalization import require_tenant_id
from runtime.queue.backpressure_monitor import BackpressureMonitor, QueueBackpressureReport, TenantPressureReader
from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_alerts import QueueAlert, QueueAlertPublishReport, QueueAlertRouter
from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore
from runtime.queue.queue_slo import QueueSLOEvaluator, QueueSLOReport

CANON_RUNTIME_QUEUE_HEALTH_MONITOR = True

PressureReaderFactory = Callable[[str, str, datetime], TenantPressureReader | None]


@dataclass(frozen=True)
class QueueHealthMonitorReport:
    tenant_id: str
    queue_name: str
    slo: QueueSLOReport
    alerts: tuple[QueueAlert, ...]
    sampled_at: datetime
    backpressure: QueueBackpressureReport | None = None
    alert_delivery: QueueAlertPublishReport | None = None


class QueueHealthMonitor:
    def __init__(
        self,
        *,
        evaluator: QueueSLOEvaluator,
        alert_router: QueueAlertRouter | None = None,
        rollup_store: SqliteQueueMetricsRollupStore | None = None,
        backpressure_monitor: BackpressureMonitor | None = None,
        pressure_reader_factory: PressureReaderFactory | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._alert_router = alert_router
        self._rollup_store = rollup_store
        self._backpressure_monitor = backpressure_monitor
        self._pressure_reader_factory = pressure_reader_factory

    def sample(self, *, tenant_id: str, queue_name: str, now: datetime | None = None) -> QueueHealthMonitorReport:
        moment = normalize_now(now)
        tid = require_tenant_id(tenant_id)
        qn = str(queue_name).strip()
        if not qn:
            raise ValueError("queue_name is required")
        slo = self._evaluator.evaluate(tenant_id=tid, queue_name=qn, now=moment)
        alerts: tuple[QueueAlert, ...] = ()
        if self._alert_router is not None:
            alerts = self._alert_router.route_from_report(report=slo, now=moment)
        backpressure = self._sample_backpressure(tenant_id=tid, queue_name=qn, now=moment)
        if backpressure is not None and backpressure.alerts:
            alerts = self._merge_alerts(alerts, backpressure.alerts)
        alert_delivery = None if self._alert_router is None else self._alert_router.last_publish_report()
        if self._rollup_store is not None:
            self._rollup_store.record_sample(
                report=slo,
                alert_count=len(alerts),
                critical_alert_count=sum(1 for alert in alerts if str(alert.severity).strip() == "critical"),
                observed_at=moment,
            )
        return QueueHealthMonitorReport(
            tenant_id=tid,
            queue_name=qn,
            slo=slo,
            alerts=alerts,
            sampled_at=moment,
            backpressure=backpressure,
            alert_delivery=alert_delivery,
        )

    def _sample_backpressure(self, *, tenant_id: str, queue_name: str, now: datetime) -> QueueBackpressureReport | None:
        if self._backpressure_monitor is None or self._pressure_reader_factory is None:
            return None
        reader = self._pressure_reader_factory(tenant_id, queue_name, now)
        if reader is None:
            return None
        return self._backpressure_monitor.sample(queue_name=queue_name, pressure_reader=reader, now=now)

    @staticmethod
    def _merge_alerts(*groups: tuple[QueueAlert, ...]) -> tuple[QueueAlert, ...]:
        merged: list[QueueAlert] = []
        seen: set[tuple[str, str, str]] = set()
        for group in groups:
            for alert in group:
                key = (str(alert.tenant_id).strip(), str(alert.queue_name).strip(), str(alert.code).strip())
                if key in seen:
                    continue
                seen.add(key)
                merged.append(alert)
        merged.sort(key=lambda item: (item.created_at, str(item.code)), reverse=True)
        return tuple(merged)


__all__ = [
    "CANON_RUNTIME_QUEUE_HEALTH_MONITOR",
    "PressureReaderFactory",
    "QueueHealthMonitor",
    "QueueHealthMonitorReport",
]
