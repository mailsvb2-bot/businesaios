from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from threading import Lock
from typing import Any

from core.events.log_queries import (
    direct_latest_append_seq,
    event_append_seq,
    iter_events as iter_event_window,
)
from core.experiments.builders.live_canary_assignment import ExperimentArm
from core.experiments.events.live_canary_events import (
    CANDIDATE_ACTION_EXECUTED,
    LIVE_CANARY_EVENT_TYPES,
)
from core.experiments.repositories.live_canary_ledger import (
    LiveCanaryLedger as _BaseLiveCanaryLedger,
    _finite,
)


def _data(event: Any) -> dict[str, Any]:
    return dict(event) if isinstance(event, Mapping) else vars(event)


def _payload(event: Any) -> dict[str, Any]:
    return dict(_data(event).get("payload") or {})


def _event_key(event: Any) -> str:
    data = _data(event)
    digest = hashlib.sha256(
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return digest


class LiveCanaryLedger(_BaseLiveCanaryLedger):
    """Live-canary ledger materialized by durable store append order."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._evidence_lock = Lock()
        self._append_cursor = 0
        self._materialized_keys: set[str] = set()
        self._materialized_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def _refresh_materialized_rows(self) -> None:
        tail = direct_latest_append_seq(self.event_log)
        with self._evidence_lock:
            after_append_seq = self._append_cursor
        if tail is not None and tail <= after_append_seq:
            return
        events = list(
            iter_event_window(
                self.event_log,
                start_ms=0,
                after_append_seq=after_append_seq,
                event_types=LIVE_CANARY_EVENT_TYPES,
            )
        )
        events.sort(key=lambda event: (event_append_seq(event), _event_key(event)))
        with self._evidence_lock:
            for event in events:
                append_seq = event_append_seq(event)
                if append_seq <= self._append_cursor:
                    continue
                key = _event_key(event)
                if self._belongs(event) and key not in self._materialized_keys:
                    self._materialized_keys.add(key)
                    self._materialized_rows.append(
                        (_data(event), _payload(event))
                    )
                self._append_cursor = append_seq
            if tail is not None:
                self._append_cursor = max(self._append_cursor, tail)

    def _experiment_rows(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        self._refresh_materialized_rows()
        with self._evidence_lock:
            return list(self._materialized_rows)

    def metrics(
        self,
        *,
        candidate_pct: float | None = None,
    ) -> dict[str, float | int]:
        metrics = super().metrics(candidate_pct=candidate_pct)
        rows = self._experiment_rows()
        assignments = self._assignments(rows, None)
        cutoff_ms = int(time.time() * 1000) - 24 * 60 * 60 * 1000
        executed_decisions: set[str] = set()
        execution_keys: set[tuple[str, str]] = set()
        actual_cost = 0.0
        for data, payload in rows:
            kind = str(data.get("event_type") or "")
            if kind != CANDIDATE_ACTION_EXECUTED:
                continue
            decision_id = str(data.get("decision_id") or "")
            assignment = assignments.get(decision_id)
            if (
                assignment is None
                or str(assignment.get("arm") or "")
                != ExperimentArm.CANDIDATE.value
            ):
                continue
            executed_at_ms = int(payload.get("executed_at_ms") or 0)
            if executed_at_ms < cutoff_ms:
                continue
            key = (decision_id, kind)
            if key in execution_keys:
                continue
            execution_keys.add(key)
            executed_decisions.add(decision_id)
            actual_cost += _finite(payload.get("cost"))

        pending_cost = sum(
            _finite(assignment.get("expected_cost"))
            for decision_id, assignment in assignments.items()
            if str(assignment.get("arm") or "")
            == ExperimentArm.CANDIDATE.value
            and int(assignment.get("assigned_at_ms") or 0) >= cutoff_ms
            and decision_id not in executed_decisions
        )
        metrics["candidate_actual_cost_24h"] = actual_cost
        metrics["candidate_cost_24h"] = actual_cost + pending_cost
        return metrics


__all__ = ["LiveCanaryLedger"]
