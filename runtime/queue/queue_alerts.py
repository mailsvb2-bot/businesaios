from __future__ import annotations

"""Queue alert derivation and routing for operational health.

This module derives alerts from queue health signals only.
It must not mutate queue state or become policy/planning logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Protocol, runtime_checkable

from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_operational_contracts import QueueAlert, QueueSLOReport
from runtime.queue.queue_slo import QueueSLOEvaluator

CANON_RUNTIME_QUEUE_ALERTS = True




@dataclass(frozen=True)
class QueueAlertCooldownPolicy:
    cooldown_seconds: int = 60

    def should_publish(
        self,
        *,
        current: QueueAlert,
        previous_published_at: datetime | None,
        now: datetime | None = None,
    ) -> bool:
        if previous_published_at is None:
            return True
        moment = normalize_now(now or current.created_at)
        return int((moment - previous_published_at).total_seconds()) >= max(0, int(self.cooldown_seconds))


@runtime_checkable
class QueueAlertSink(Protocol):
    def publish(self, alerts: tuple[QueueAlert, ...]) -> None: ...

    def publish_with_report(self, alerts: tuple[QueueAlert, ...]) -> QueueAlertPublishReport: ...


@dataclass(frozen=True)
class QueueAlertPublishReport:
    attempted: int
    published: int
    suppressed: int
    published_alerts: tuple[QueueAlert, ...] = field(default_factory=tuple)

    @property
    def had_suppression(self) -> bool:
        return int(self.suppressed) > 0


class InMemoryQueueAlertSink(QueueAlertSink):
    def __init__(self) -> None:
        self._lock = RLock()
        self._alerts: list[QueueAlert] = []

    def publish(self, alerts: tuple[QueueAlert, ...]) -> None:
        self.publish_with_report(alerts)

    def publish_with_report(self, alerts: tuple[QueueAlert, ...]) -> QueueAlertPublishReport:
        with self._lock:
            self._alerts.extend(alerts)
        return QueueAlertPublishReport(
            attempted=len(alerts),
            published=len(alerts),
            suppressed=0,
            published_alerts=tuple(alerts),
        )

    def snapshot(self) -> tuple[QueueAlert, ...]:
        with self._lock:
            return tuple(self._alerts)


class CooldownQueueAlertSink(QueueAlertSink):
    """Suppress duplicate alerts for a bounded cooldown window.

    This is an operational de-noising layer only. It does not hide alerts from
    observability snapshots because the router still records derived alerts.
    It only suppresses repeated downstream delivery.
    """

    def __init__(
        self,
        *,
        inner: QueueAlertSink,
        cooldown_policy: QueueAlertCooldownPolicy | None = None,
    ) -> None:
        self._inner = inner
        self._cooldown_policy = cooldown_policy or QueueAlertCooldownPolicy()
        self._lock = RLock()
        self._last_published_at: dict[tuple[str, str, str], datetime] = {}

    def publish(self, alerts: tuple[QueueAlert, ...]) -> None:
        self.publish_with_report(alerts)

    def publish_with_report(self, alerts: tuple[QueueAlert, ...]) -> QueueAlertPublishReport:
        allowed = self._filter(alerts)
        if allowed:
            inner_publish = getattr(self._inner, 'publish_with_report', None)
            if callable(inner_publish):
                inner_publish(tuple(allowed))
            else:
                self._inner.publish(tuple(allowed))
        return QueueAlertPublishReport(
            attempted=len(alerts),
            published=len(allowed),
            suppressed=max(0, len(alerts) - len(allowed)),
            published_alerts=tuple(allowed),
        )

    def _filter(self, alerts: tuple[QueueAlert, ...]) -> tuple[QueueAlert, ...]:
        allowed: list[QueueAlert] = []
        with self._lock:
            for alert in alerts:
                key = (
                    str(alert.tenant_id).strip(),
                    str(alert.queue_name).strip(),
                    str(alert.code).strip(),
                )
                previous = self._last_published_at.get(key)
                if self._cooldown_policy.should_publish(
                    current=alert,
                    previous_published_at=previous,
                    now=alert.created_at,
                ):
                    self._last_published_at[key] = normalize_now(alert.created_at)
                    allowed.append(alert)
        return tuple(allowed)


class QueueAlertRouter:
    def __init__(
        self,
        *,
        evaluator: QueueSLOEvaluator,
        observability: object | None = None,
        sink: QueueAlertSink | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._observability = observability
        self._sink = sink
        self._last_publish_report = QueueAlertPublishReport(attempted=0, published=0, suppressed=0, published_alerts=())

    def evaluate_and_route(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        now: datetime | None = None,
    ) -> tuple[QueueAlert, ...]:
        moment = normalize_now(now)
        report = self._evaluator.evaluate(tenant_id=tenant_id, queue_name=queue_name, now=moment)
        return self.route_from_report(report=report, now=moment)

    def route_from_report(self, *, report: QueueSLOReport, now: datetime | None = None) -> tuple[QueueAlert, ...]:
        moment = normalize_now(now)
        alerts = self._alerts_from_report(report=report, now=moment)
        self._publish(alerts=alerts, now=moment)
        if self._observability is not None:
            self._observability.record_alerts(alerts, now=moment)
        return alerts

    def _publish(self, *, alerts: tuple[QueueAlert, ...], now: datetime) -> None:
        if not alerts:
            self._last_publish_report = QueueAlertPublishReport(attempted=0, published=0, suppressed=0, published_alerts=())
            return
        if self._sink is None:
            self._last_publish_report = QueueAlertPublishReport(
                attempted=len(alerts),
                published=0,
                suppressed=0,
                published_alerts=(),
            )
            return
        publish_with_report = getattr(self._sink, 'publish_with_report', None)
        if callable(publish_with_report):
            self._last_publish_report = publish_with_report(alerts)
            return
        self._sink.publish(alerts)
        self._last_publish_report = QueueAlertPublishReport(
            attempted=len(alerts),
            published=len(alerts),
            suppressed=0,
            published_alerts=tuple(alerts),
        )

    @staticmethod
    def _alerts_from_report(*, report: QueueSLOReport, now: datetime) -> tuple[QueueAlert, ...]:
        alerts: list[QueueAlert] = []
        for reason in report.reasons:
            severity = 'warning'
            if reason in {'dead_letter_jobs_exceeded', 'leadership_stale', 'janitor_stale'}:
                severity = 'critical'
            elif reason in {'pending_jobs_exceeded', 'active_claims_exceeded'}:
                severity = 'error'
            alerts.append(
                QueueAlert(
                    tenant_id=report.tenant_id,
                    queue_name=report.queue_name,
                    code=reason,
                    severity=severity,
                    message=QueueAlertRouter._message_for_reason(report=report, reason=reason),
                    created_at=now,
                )
            )
        return tuple(alerts)

    def last_publish_report(self) -> QueueAlertPublishReport:
        return self._last_publish_report

    @staticmethod
    def _message_for_reason(*, report: QueueSLOReport, reason: str) -> str:
        if reason == 'pending_jobs_exceeded':
            return f'Queue pending depth exceeded: {report.pending_jobs}'
        if reason == 'active_claims_exceeded':
            return f'Queue active claims exceeded: {report.active_claims}'
        if reason == 'dead_letter_jobs_exceeded':
            return f'Queue dead-letter pressure exceeded: {report.dead_letter_jobs}'
        if reason == 'janitor_stale':
            return f'Queue janitor appears stale: age={report.janitor_stale_seconds}'
        if reason == 'leadership_stale':
            return f'Queue leadership appears stale: age={report.leader_stale_seconds}'
        return reason


__all__ = [
    'CANON_RUNTIME_QUEUE_ALERTS',
    'CooldownQueueAlertSink',
    'InMemoryQueueAlertSink',
    'QueueAlertPublishReport',
    'QueueAlert',
    'QueueAlertCooldownPolicy',
    'QueueAlertRouter',
    'QueueAlertSink',
]
