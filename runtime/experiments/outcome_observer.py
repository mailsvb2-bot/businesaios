from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from threading import Event, Lock, Thread
from typing import Any

from core.experiments.guardrails import CanaryDecision, GuardrailResult
from core.experiments.live_canary_events import BUSINESS_OUTCOME_OBSERVED
from runtime.experiments.live_canary import (
    LiveCanaryCoordinator,
    source_event_evidence_ref,
)

log = logging.getLogger(__name__)


def _data(event: Any) -> dict[str, Any]:
    return dict(event) if isinstance(event, Mapping) else vars(event)


def _payload(event: Any) -> dict[str, Any]:
    return dict(_data(event).get("payload") or {})


def _success(payload: Mapping[str, Any]) -> bool | None:
    for key in ("success", "ok"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _observed_at_ms(event: Any, payload: Mapping[str, Any]) -> int:
    data = _data(event)
    for source in (payload, data):
        for key in (
            "observed_at_ms",
            "event_time_ms",
            "emitted_at_ms",
            "timestamp_ms",
            "created_at_ms",
        ):
            value = source.get(key)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
    return int(time.time() * 1000)



class LiveCanaryOutcomeObserver:
    """Bind real source events to canary assignments from the shared ledger."""

    def __init__(self, coordinator: LiveCanaryCoordinator) -> None:
        self.coordinator = coordinator

    def poll_once(self) -> int:
        iterator = getattr(self.coordinator.event_log, "iter_events", None)
        if not callable(iterator):
            raise RuntimeError("LIVE_CANARY_EVENT_LEDGER_UNAVAILABLE")
        recorded = 0
        for event in list(iterator()):
            data = _data(event)
            event_type = str(data.get("event_type") or "")
            if event_type not in self.coordinator.policy.outcome_event_types:
                continue
            if str(data.get("source") or "") == "live_canary":
                continue
            decision_id = str(data.get("decision_id") or "").strip()
            if not decision_id:
                continue
            assignment = self.coordinator.ledger.assignment_for_decision(decision_id)
            if assignment is None or assignment.get("eligible") is not True:
                continue
            payload = _payload(event)
            success = _success(payload)
            if success is None:
                continue
            evidence_ref = source_event_evidence_ref(event)
            already_attributed = any(
                _payload(existing).get("outcome_type") == event_type
                and _payload(existing).get("evidence_ref") == evidence_ref
                for existing in self.coordinator.ledger.events_for_decision(
                    decision_id, BUSINESS_OUTCOME_OBSERVED
                )
            )
            if already_attributed:
                continue
            try:
                self.coordinator.record_outcome(
                    decision_id=decision_id,
                    correlation_id=(
                        str(data.get("correlation_id") or "").strip() or None
                    ),
                    arm=str(assignment.get("arm") or ""),
                    outcome_type=event_type,
                    success=success,
                    evidence_ref=evidence_ref,
                    observed_at_ms=_observed_at_ms(event, payload),
                )
                recorded += 1
            except RuntimeError as exc:
                if str(exc).startswith("LIVE_CANARY_IDEMPOTENCY_CONFLICT"):
                    result = GuardrailResult(
                        CanaryDecision.ROLLBACK,
                        ("outcome_idempotency_conflict",),
                        {},
                    )
                    self.coordinator._open_local_circuit(
                        result,
                        decision_id=f"outcome-observer:{decision_id}",
                        correlation_id=(
                            str(data.get("correlation_id") or "").strip() or None
                        ),
                        tenant_id=str(assignment.get("tenant_id") or ""),
                    )
                elif str(exc) not in {
                    "LIVE_CANARY_OUTCOME_WINDOW_EXPIRED",
                    "LIVE_CANARY_OUTCOME_PRECEDES_ASSIGNMENT",
                }:
                    log.warning(
                        "live_canary_outcome_observer_rejected event=%s error=%s",
                        event_type,
                        exc,
                    )
        return recorded


class LiveCanaryOutcomeSupervisor:
    """Own the lifecycle of automatic outcome attribution."""

    def __init__(
        self,
        observer: LiveCanaryOutcomeObserver,
        *,
        interval_seconds: float,
    ) -> None:
        if interval_seconds < 1:
            raise ValueError("interval_seconds must be at least one")
        self.observer = observer
        self.interval_seconds = float(interval_seconds)
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("live canary outcome supervisor already started")
            self._thread = Thread(
                target=self._run,
                name="live-canary-outcome-observer",
                daemon=True,
            )
            self._thread.start()

    def request_stop(self) -> None:
        self._stop.set()

    def join(self, *, timeout_seconds: float = 10.0) -> None:
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.0, float(timeout_seconds)))

    def pulse_once(self) -> int:
        return self.observer.poll_once()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.observer.poll_once()
            except Exception as exc:
                result = GuardrailResult(
                    CanaryDecision.ROLLBACK,
                    (f"outcome_observer_error:{type(exc).__name__}",),
                    {},
                )
                self.observer.coordinator._open_local_circuit(
                    result,
                    decision_id="outcome-observer-supervisor",
                    correlation_id=(
                        "live-canary:"
                        + self.observer.coordinator.policy.experiment_id
                    ),
                    tenant_id=(
                        self.observer.coordinator.policy.allowed_tenant_ids[0]
                    ),
                )
                return
            self._stop.wait(self.interval_seconds)


__all__ = ["LiveCanaryOutcomeObserver", "LiveCanaryOutcomeSupervisor"]
