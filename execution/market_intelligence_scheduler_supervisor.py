"""Lifecycle-only supervisor for managed market-intelligence scheduling.

This module owns thread lifecycle only:
- start polling loop
- request graceful stop
- join and return execution report
- expose health snapshot

It must not introduce provider ranking, planning, or an alternate decision path.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import time
from typing import Any
from execution.market_intelligence_scheduler_service import MarketIntelligenceSchedulerService
from runtime.runtime_observability import RuntimeObservability

CANON_MARKET_INTELLIGENCE_SCHEDULER_SUPERVISOR = True
CANON_MARKET_INTELLIGENCE_SCHEDULER_SUPERVISOR_NO_DECISION_LOGIC = True

@dataclass(frozen=True)
class MarketIntelligenceSupervisorReport:
    tenant_id: str
    pulses: int
    total_results: int
    executed_results: int
    started_at_epoch: float | None
    stopped_at_epoch: float | None
    stop_reason: str | None


@dataclass(frozen=True)
class MarketIntelligenceSupervisorHandle:
    tenant_id: str
    thread_name: str
    is_alive: bool
    started_at_epoch: float | None
    stop_requested: bool
    last_report: MarketIntelligenceSupervisorReport | None


class MarketIntelligenceSchedulerSupervisor:
    def __init__(
        self,
        *,
        scheduler: MarketIntelligenceSchedulerService,
        tenant_id: str = "tenant-default",
        active_campaign_tags: tuple[str, ...] = (),
        poll_interval_seconds: float = 5.0,
        observability: RuntimeObservability | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._tenant_id = str(tenant_id).strip() or "tenant-default"
        self._active_campaign_tags = tuple(str(item).strip() for item in active_campaign_tags if str(item).strip())
        self._poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        self._observability = observability
        self._lock = Lock()
        self._thread: Thread | None = None
        self._stop = Event()
        self._started_at_epoch: float | None = None
        self._stop_reason: str | None = None
        self._pulses = 0
        self._total_results = 0
        self._executed_results = 0
        self._last_report: MarketIntelligenceSupervisorReport | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("market-intelligence supervisor already started")
            self._started_at_epoch = time()
            self._thread = Thread(
                target=self._run_loop,
                name=f"market-intelligence-supervisor-{self._tenant_id}",
                daemon=True,
            )
            self._thread.start()
            self._record_audit_event("market_intelligence_supervisor_started", poll_interval_seconds=self._poll_interval_seconds)

    def pulse_once(self) -> tuple[dict[str, Any], ...]:
        results = self._scheduler.run_due(
            tenant_id=self._tenant_id,
            active_campaign_tags=self._active_campaign_tags,
        )
        executed_results = sum(1 for item in results if bool(item.get("executed", item.get("ok"))))
        with self._lock:
            self._pulses += 1
            self._total_results += len(results)
            self._executed_results += executed_results
            self._last_report = self._build_report(stopped_at_epoch=None)
        self._record_audit_event("market_intelligence_supervisor_pulsed", results_count=len(results), executed_results=executed_results)
        return results

    def request_stop(self, *, reason: str = "supervisor_stop") -> None:
        with self._lock:
            self._stop_reason = str(reason).strip() or "supervisor_stop"
            self._stop.set()
        self._record_audit_event("market_intelligence_supervisor_stop_requested", reason=self._stop_reason or "supervisor_stop")

    def join(self, *, timeout_seconds: float = 10.0) -> MarketIntelligenceSupervisorReport:
        thread = None
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.0, float(timeout_seconds)))
        with self._lock:
            if self._last_report is None:
                self._last_report = self._build_report(stopped_at_epoch=time())
            report = self._last_report
        self._record_audit_event("market_intelligence_supervisor_joined", pulses=report.pulses, executed_results=report.executed_results)
        return report

    def snapshot(self) -> MarketIntelligenceSupervisorHandle:
        with self._lock:
            thread = self._thread
            return MarketIntelligenceSupervisorHandle(
                tenant_id=self._tenant_id,
                thread_name=(thread.name if thread is not None else f"market-intelligence-supervisor-{self._tenant_id}"),
                is_alive=(thread.is_alive() if thread is not None else False),
                started_at_epoch=self._started_at_epoch,
                stop_requested=self._stop.is_set(),
                last_report=self._last_report,
            )

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            self.pulse_once()
            if self._stop.wait(self._poll_interval_seconds):
                break
        with self._lock:
            self._last_report = self._build_report(stopped_at_epoch=time())
        self._record_audit_event("market_intelligence_supervisor_stopped", reason=self._stop_reason or "loop_completed")


    def _record_audit_event(self, event_name: str, **fields: Any) -> None:
        if self._observability is None:
            return
        payload = {'tenant_id': self._tenant_id}
        payload.update(dict(fields))
        self._observability.record_audit_event(event_name, **payload)

    def _build_report(self, *, stopped_at_epoch: float | None) -> MarketIntelligenceSupervisorReport:
        return MarketIntelligenceSupervisorReport(
            tenant_id=self._tenant_id,
            pulses=int(self._pulses),
            total_results=int(self._total_results),
            executed_results=int(self._executed_results),
            started_at_epoch=self._started_at_epoch,
            stopped_at_epoch=stopped_at_epoch,
            stop_reason=self._stop_reason,
        )


__all__ = [
    "CANON_MARKET_INTELLIGENCE_SCHEDULER_SUPERVISOR",
    "CANON_MARKET_INTELLIGENCE_SCHEDULER_SUPERVISOR_NO_DECISION_LOGIC",
    "MarketIntelligenceSchedulerSupervisor",
    "MarketIntelligenceSupervisorHandle",
    "MarketIntelligenceSupervisorReport",
]
