from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Mapping
from typing import Any

from core.experiments.guardrails import CanaryDecision, GuardrailResult
from runtime.experiments.live_canary import LiveCanaryCoordinator

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


def _evidence_ref(event: Any) -> str:
    data = _data(event)
    for key in ("event_id", "id", "external_id"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return f"event:{str(value).strip()}"
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"event-sha256:{digest}"


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
            try:
                self.coordinator.record_outcome(
                    decision_id=decision_id,
                    correlation_id=(
                        str(data.get("correlation_id") or "").strip() or None
                    ),
                    arm=str(assignment.get("arm") or ""),
                    outcome_type=event_type,
                    success=success,
                    evidence_ref=_evidence_ref(event),
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


__all__ = ["LiveCanaryOutcomeObserver"]
