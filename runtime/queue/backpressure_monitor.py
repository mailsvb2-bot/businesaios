from __future__ import annotations

"""Read-only queue pressure/fairness monitor."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable
from collections.abc import Iterable

from runtime.queue.backpressure_policy import BackpressurePolicy, BackpressureVerdict
from runtime.queue.job_contract import JobState, normalize_now
from runtime.queue.job_store_backend import JobStoreBackend
from runtime.queue.queue_alerts import QueueAlert
from runtime.queue.queue_observability import QueueObservabilityRegistry
from runtime.queue.tenant_fair_scheduler import (
    TenantFairAllocation,
    TenantFairScheduler,
    TenantFairScheduleReport,
    TenantQueuePressure,
)

CANON_RUNTIME_QUEUE_BACKPRESSURE_MONITOR = True


@dataclass(frozen=True)
class TenantBackpressureStatus:
    tenant_id: str
    queue_name: str
    pending_jobs: int
    active_claims: int
    oldest_pending_age_seconds: int
    verdict: BackpressureVerdict
    fair_allocation: TenantFairAllocation | None = None

    @property
    def fairness_gap(self) -> int:
        expected = 0 if self.fair_allocation is None else int(self.fair_allocation.claim_limit)
        return max(0, int(self.pending_jobs) - expected)


@dataclass(frozen=True)
class QueueBackpressureReport:
    queue_name: str
    total_pending_jobs: int
    total_active_claims: int
    global_verdict: BackpressureVerdict
    fair_schedule: TenantFairScheduleReport
    tenant_statuses: tuple[TenantBackpressureStatus, ...]
    alerts: tuple[QueueAlert, ...]
    sampled_at: datetime

    @property
    def is_under_pressure(self) -> bool:
        return (not self.global_verdict.allowed) or self.global_verdict.reason != "normal"

    @property
    def starving_tenants(self) -> int:
        return sum(1 for item in self.tenant_statuses if item.fair_allocation is not None and bool(item.fair_allocation.starving))


@runtime_checkable
class TenantPressureReader(Protocol):
    def read_pressures(self, *, queue_name: str, now: datetime | None = None) -> tuple[TenantQueuePressure, ...]: ...


@dataclass(frozen=True)
class StoreTenantPressureReader:
    store: JobStoreBackend
    tenant_ids: tuple[str, ...]
    oldest_pending_age_seconds: dict[str, int] = field(default_factory=dict)
    weights: dict[str, int] = field(default_factory=dict)

    def read_pressures(self, *, queue_name: str, now: datetime | None = None) -> tuple[TenantQueuePressure, ...]:
        normalize_now(now)
        queue = str(queue_name).strip()
        if not queue:
            raise ValueError("queue_name is required")
        from core.tenancy.normalization import require_tenant_id
        seen: set[str] = set()
        result: list[TenantQueuePressure] = []
        for tenant_id in self.tenant_ids:
            tid = require_tenant_id(tenant_id)
            if tid in seen:
                continue
            seen.add(tid)
            pending = int(self.store.count(tenant_id=tid, queue_name=queue, state=JobState.PENDING))
            active = int(self.store.count(tenant_id=tid, queue_name=queue, state=JobState.CLAIMED))
            if pending <= 0 and active <= 0:
                continue
            result.append(
                TenantQueuePressure(
                    tenant_id=tid,
                    queue_name=queue,
                    pending_jobs=pending,
                    active_claims=active,
                    oldest_pending_age_seconds=max(0, int(self.oldest_pending_age_seconds.get(tid, 0))),
                    weight=max(1, int(self.weights.get(tid, 1))),
                )
            )
        return tuple(result)


class BackpressureMonitor:
    def __init__(
        self,
        *,
        policy: BackpressurePolicy | None = None,
        fair_scheduler: TenantFairScheduler | None = None,
        observability: QueueObservabilityRegistry | None = None,
    ) -> None:
        self._policy = policy or BackpressurePolicy()
        self._fair_scheduler = fair_scheduler or TenantFairScheduler()
        self._observability = observability

    def sample(
        self,
        *,
        queue_name: str,
        pressure_reader: TenantPressureReader,
        total_claim_limit: int | None = None,
        now: datetime | None = None,
    ) -> QueueBackpressureReport:
        moment = normalize_now(now)
        queue = str(queue_name).strip()
        if not queue:
            raise ValueError("queue_name is required")
        pressures = tuple(pressure_reader.read_pressures(queue_name=queue, now=moment))
        total_pending = sum(int(item.pending_jobs) for item in pressures)
        total_active = sum(int(item.active_claims) for item in pressures)
        global_verdict = self._policy.evaluate(queue_depth=total_pending, claimed_depth=total_active)
        fair_schedule = self._fair_scheduler.plan_allocations(queue_name=queue, pressures=pressures, total_claim_limit=total_claim_limit, now=moment)
        allocation_by_tenant = {item.tenant_id: item for item in fair_schedule.allocations}
        tenant_statuses = tuple(
            TenantBackpressureStatus(
                tenant_id=item.tenant_id,
                queue_name=item.queue_name,
                pending_jobs=int(item.pending_jobs),
                active_claims=int(item.active_claims),
                oldest_pending_age_seconds=int(item.oldest_pending_age_seconds),
                verdict=self._policy.evaluate(queue_depth=int(item.pending_jobs), claimed_depth=int(item.active_claims)),
                fair_allocation=allocation_by_tenant.get(item.tenant_id),
            )
            for item in sorted(pressures, key=lambda value: (-int(value.pending_jobs), -int(value.oldest_pending_age_seconds), int(value.active_claims), value.tenant_id))
        )
        alerts = self._derive_alerts(queue_name=queue, global_verdict=global_verdict, tenant_statuses=tenant_statuses, sampled_at=moment)
        if alerts and self._observability is not None:
            self._observability.record_alerts(alerts, now=moment)
        return QueueBackpressureReport(queue, total_pending, total_active, global_verdict, fair_schedule, tenant_statuses, alerts, moment)

    def sample_from_store(
        self,
        *,
        store: JobStoreBackend,
        queue_name: str,
        tenant_ids: Iterable[str],
        total_claim_limit: int | None = None,
        oldest_pending_age_seconds: dict[str, int] | None = None,
        weights: dict[str, int] | None = None,
        now: datetime | None = None,
    ) -> QueueBackpressureReport:
        reader = StoreTenantPressureReader(store=store, tenant_ids=tuple(tenant_ids), oldest_pending_age_seconds=dict(oldest_pending_age_seconds or {}), weights=dict(weights or {}))
        return self.sample(queue_name=queue_name, pressure_reader=reader, total_claim_limit=total_claim_limit, now=now)

    @staticmethod
    def _derive_alerts(*, queue_name: str, global_verdict: BackpressureVerdict, tenant_statuses: tuple[TenantBackpressureStatus, ...], sampled_at: datetime) -> tuple[QueueAlert, ...]:
        alerts: list[QueueAlert] = []
        if global_verdict.reason != "normal":
            severity = "critical" if not global_verdict.allowed else "warning"
            alerts.append(QueueAlert(tenant_id="*", queue_name=queue_name, code=global_verdict.reason, severity=severity, message=f"queue backpressure: reason={global_verdict.reason} delay={int(global_verdict.suggested_delay_seconds)}s", created_at=sampled_at))
        for status in tenant_statuses:
            if status.verdict.reason != "normal":
                severity = "critical" if not status.verdict.allowed else "warning"
                alerts.append(QueueAlert(tenant_id=status.tenant_id, queue_name=status.queue_name, code=status.verdict.reason, severity=severity, message=f"tenant queue pressure: pending={status.pending_jobs} active={status.active_claims}", created_at=sampled_at))
            allocation = status.fair_allocation
            if allocation is not None and allocation.starving:
                alerts.append(QueueAlert(tenant_id=status.tenant_id, queue_name=status.queue_name, code="tenant_starvation_risk", severity="warning", message=f"starvation risk: oldest_pending_age_seconds={status.oldest_pending_age_seconds} allocated_claims={allocation.claim_limit} pending={status.pending_jobs}", created_at=sampled_at))
            if status.fairness_gap > max(1, status.pending_jobs // 2):
                alerts.append(QueueAlert(tenant_id=status.tenant_id, queue_name=status.queue_name, code="tenant_fairness_gap_high", severity="warning", message=f"fairness gap high: pending={status.pending_jobs} expected_allocated={0 if allocation is None else allocation.claim_limit}", created_at=sampled_at))
        return tuple(alerts)


__all__ = [
    "BackpressureMonitor",
    "CANON_RUNTIME_QUEUE_BACKPRESSURE_MONITOR",
    "QueueBackpressureReport",
    "StoreTenantPressureReader",
    "TenantBackpressureStatus",
    "TenantPressureReader",
]
