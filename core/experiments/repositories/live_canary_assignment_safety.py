from __future__ import annotations

import time
from collections import Counter, deque
from collections.abc import Mapping
from threading import Lock
from typing import Any

from core.events.log_queries import (
    event_timestamp_ms,
    iter_events as iter_event_window,
)
from core.experiments.assignment import ExperimentArm, ExperimentAssignment
from core.experiments.live_canary_events import EXPERIMENT_ASSIGNMENT


def _data(event: Any) -> dict[str, Any]:
    return dict(event) if isinstance(event, Mapping) else vars(event)


def _payload(event: Any) -> dict[str, Any]:
    return dict(_data(event).get("payload") or {})


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number and abs(number) != float("inf") else default


class LiveCanaryAssignmentSafety:
    """Materialized assignment guard state refreshed from shared evidence."""

    def __init__(
        self,
        event_log: Any,
        *,
        experiment_id: str,
        candidate_policy_id: str,
    ) -> None:
        self.event_log = event_log
        self.experiment_id = str(experiment_id)
        self.candidate_policy_id = str(candidate_policy_id)
        self._lock = Lock()
        self._loaded = False
        self._cursor_ms = 0
        self._seen_decisions_at_cursor: set[str] = set()
        self._decision_ids: set[str] = set()
        self._stage_counts: dict[float, Counter[str]] = {}
        self._stage_first_assignment_ms: dict[float, int] = {}
        self._candidate_window: deque[tuple[int, str, float]] = deque()
        self._candidate_expected_cost = 0.0
        self._candidate_subject_counts: Counter[str] = Counter()
        self._candidate_max_subject_count = 0

    def _belongs(self, event: Any) -> bool:
        payload = _payload(event)
        return (
            payload.get("experiment_id") == self.experiment_id
            and payload.get("candidate_policy_id") == self.candidate_policy_id
        )

    def _track(
        self,
        *,
        decision_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        if payload.get("eligible") is not True:
            return
        did = str(decision_id)
        if not did or did in self._decision_ids:
            return
        self._decision_ids.add(did)
        stage = float(payload.get("candidate_pct") or 0.0)
        arm = str(payload.get("arm") or "")
        self._stage_counts.setdefault(stage, Counter())[arm] += 1
        assigned_at_ms = int(payload.get("assigned_at_ms") or 0)
        first = self._stage_first_assignment_ms.get(stage, 0)
        if assigned_at_ms and (not first or assigned_at_ms < first):
            self._stage_first_assignment_ms[stage] = assigned_at_ms
        if arm != ExperimentArm.CANDIDATE.value:
            return
        subject_hash = str(payload.get("subject_hash") or "")
        expected_cost = _finite(payload.get("expected_cost"))
        self._candidate_window.append(
            (assigned_at_ms, subject_hash, expected_cost)
        )
        self._candidate_expected_cost += expected_cost
        self._candidate_subject_counts[subject_hash] += 1
        self._candidate_max_subject_count = max(
            self._candidate_max_subject_count,
            self._candidate_subject_counts[subject_hash],
        )

    def refresh(self) -> None:
        """Consume newly appended shared assignment rows before guard checks."""

        with self._lock:
            cursor_ms = self._cursor_ms
            seen_at_cursor = set(self._seen_decisions_at_cursor)
        rows = [
            event
            for event in iter_event_window(
                self.event_log,
                start_ms=cursor_ms,
                event_types=(EXPERIMENT_ASSIGNMENT,),
            )
            if self._belongs(event)
        ]
        rows.sort(
            key=lambda event: (
                event_timestamp_ms(event),
                str(_data(event).get("decision_id") or ""),
            )
        )
        with self._lock:
            for event in rows:
                data = _data(event)
                decision_id = str(data.get("decision_id") or "")
                timestamp_ms = event_timestamp_ms(event)
                if timestamp_ms < self._cursor_ms:
                    continue
                if (
                    timestamp_ms == self._cursor_ms
                    and decision_id in self._seen_decisions_at_cursor
                ):
                    continue
                self._track(
                    decision_id=decision_id,
                    payload=_payload(event),
                )
                if timestamp_ms > self._cursor_ms:
                    self._cursor_ms = timestamp_ms
                    self._seen_decisions_at_cursor = {decision_id}
                else:
                    self._seen_decisions_at_cursor.add(decision_id)
            if self._cursor_ms == cursor_ms:
                self._seen_decisions_at_cursor.update(seen_at_cursor)
            self._loaded = True

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.refresh()

    def observe(
        self,
        assignment: ExperimentAssignment,
        *,
        decision_id: str,
        candidate_pct: float,
        expected_cost: float,
        assigned_at_ms: int,
    ) -> None:
        self.ensure_loaded()
        payload = {
            "eligible": assignment.eligible,
            "arm": assignment.arm.value,
            "candidate_pct": float(candidate_pct),
            "assigned_at_ms": int(assigned_at_ms),
            "subject_hash": assignment.subject_hash,
            "expected_cost": _finite(expected_cost),
        }
        with self._lock:
            self._track(decision_id=str(decision_id), payload=payload)
        self.refresh()

    def _purge_expired(self, *, cutoff_ms: int) -> None:
        max_dirty = False
        while self._candidate_window and self._candidate_window[0][0] < cutoff_ms:
            _assigned_at, subject_hash, expected_cost = (
                self._candidate_window.popleft()
            )
            self._candidate_expected_cost = max(
                0.0,
                self._candidate_expected_cost - expected_cost,
            )
            previous = self._candidate_subject_counts[subject_hash]
            if previous >= self._candidate_max_subject_count:
                max_dirty = True
            if previous <= 1:
                self._candidate_subject_counts.pop(subject_hash, None)
            else:
                self._candidate_subject_counts[subject_hash] = previous - 1
        if max_dirty:
            self._candidate_max_subject_count = max(
                self._candidate_subject_counts.values(),
                default=0,
            )

    def metrics(self, *, candidate_pct: float) -> dict[str, float | int]:
        self.refresh()
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._purge_expired(
                cutoff_ms=now_ms - 24 * 60 * 60 * 1000,
            )
            counts = self._stage_counts.get(float(candidate_pct), Counter())
            control = int(counts.get(ExperimentArm.CONTROL.value, 0))
            candidate = int(counts.get(ExperimentArm.CANDIDATE.value, 0))
            first = self._stage_first_assignment_ms.get(float(candidate_pct), 0)
            return {
                "control_assignments": control,
                "candidate_assignments": candidate,
                "mature_control_assignments": 0,
                "mature_candidate_assignments": 0,
                "control_executions": 0,
                "candidate_executions": 0,
                "control_errors": 0,
                "candidate_errors": 0,
                "control_complaints": 0,
                "candidate_complaints": 0,
                "control_cost": 0.0,
                "candidate_cost": 0.0,
                "control_outcomes": 0,
                "candidate_outcomes": 0,
                "control_successes": 0,
                "candidate_successes": 0,
                "critical_violations": 0,
                "candidate_actions_24h": len(self._candidate_window),
                "candidate_expected_cost_24h": self._candidate_expected_cost,
                "candidate_actual_cost_24h": 0.0,
                "candidate_cost_24h": self._candidate_expected_cost,
                "candidate_max_actions_per_subject_24h": (
                    self._candidate_max_subject_count
                ),
                "duration_seconds": (
                    max(0.0, (now_ms - first) / 1000.0) if first else 0.0
                ),
                "assignment_count": control + candidate,
                "mature_assignment_count": 0,
                "outcome_count": 0,
                "mature_outcome_count": 0,
            }


__all__ = ["LiveCanaryAssignmentSafety"]
