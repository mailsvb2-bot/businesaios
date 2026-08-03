from __future__ import annotations

import time
from collections import Counter, deque
from collections.abc import Mapping
from threading import Lock
from typing import Any

from core.events.log_queries import (
    direct_latest_append_seq,
    event_append_seq,
    iter_events as iter_event_window,
)
from core.experiments.assignment import ExperimentArm, ExperimentAssignment
from core.experiments.builders.live_canary_cost_semantics import (
    validate_reservation_cost,
)
from core.experiments.live_canary_events import (
    CANDIDATE_ACTION_EXECUTED,
    EXPERIMENT_ASSIGNMENT,
)


def _data(event: Any) -> dict[str, Any]:
    return dict(event) if isinstance(event, Mapping) else vars(event)


def _payload(event: Any) -> dict[str, Any]:
    return dict(_data(event).get("payload") or {})


class LiveCanaryAssignmentSafety:
    """Materialized shared guard state used before admitting assignments."""

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
        self._append_cursor = 0
        self._assignment_ids: set[str] = set()
        self._execution_ids: set[str] = set()
        self._stage_counts: dict[float, Counter[str]] = {}
        self._stage_first_assignment_ms: dict[float, int] = {}
        self._candidate_window: deque[tuple[int, str, str, float]] = deque()
        self._candidate_assignments: dict[str, tuple[int, str, float]] = {}
        self._candidate_actual_costs: dict[str, float] = {}
        self._candidate_subject_counts: Counter[str] = Counter()
        self._candidate_max_subject_count = 0

    def _belongs(self, event: Any) -> bool:
        payload = _payload(event)
        return (
            payload.get("experiment_id") == self.experiment_id
            and payload.get("candidate_policy_id") == self.candidate_policy_id
        )

    def _track_assignment(
        self,
        *,
        decision_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        if payload.get("eligible") is not True:
            return
        did = str(decision_id)
        if not did or did in self._assignment_ids:
            return
        stage = float(payload.get("candidate_pct") or 0.0)
        arm = str(payload.get("arm") or "")
        expected_cost = validate_reservation_cost(payload.get("expected_cost"))
        self._assignment_ids.add(did)
        self._stage_counts.setdefault(stage, Counter())[arm] += 1
        assigned_at_ms = int(payload.get("assigned_at_ms") or 0)
        first = self._stage_first_assignment_ms.get(stage, 0)
        if assigned_at_ms and (not first or assigned_at_ms < first):
            self._stage_first_assignment_ms[stage] = assigned_at_ms
        if arm != ExperimentArm.CANDIDATE.value:
            return
        subject_hash = str(payload.get("subject_hash") or "")
        assignment = (assigned_at_ms, subject_hash, expected_cost)
        self._candidate_assignments[did] = assignment
        self._candidate_window.append((assigned_at_ms, did, subject_hash, expected_cost))
        self._candidate_subject_counts[subject_hash] += 1
        self._candidate_max_subject_count = max(
            self._candidate_max_subject_count,
            self._candidate_subject_counts[subject_hash],
        )

    def _track_execution(
        self,
        *,
        decision_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        did = str(decision_id)
        if not did or did in self._execution_ids:
            return
        actual_cost = validate_reservation_cost(payload.get("cost"))
        self._execution_ids.add(did)
        self._candidate_actual_costs[did] = actual_cost

    def _track_event(self, event: Any) -> None:
        data = _data(event)
        event_type = str(data.get("event_type") or "")
        decision_id = str(data.get("decision_id") or "")
        payload = _payload(event)
        if event_type == EXPERIMENT_ASSIGNMENT:
            self._track_assignment(decision_id=decision_id, payload=payload)
        elif event_type == CANDIDATE_ACTION_EXECUTED:
            self._track_execution(decision_id=decision_id, payload=payload)

    def refresh(self) -> None:
        """Consume new shared assignments and executions in append order."""

        direct_tail = direct_latest_append_seq(self.event_log)
        with self._lock:
            after_append_seq = self._append_cursor
        if direct_tail is not None and direct_tail <= after_append_seq:
            return

        rows = list(
            iter_event_window(
                self.event_log,
                start_ms=0,
                after_append_seq=after_append_seq,
                event_types=(EXPERIMENT_ASSIGNMENT, CANDIDATE_ACTION_EXECUTED),
            )
        )
        rows.sort(
            key=lambda event: (
                event_append_seq(event),
                str(_data(event).get("decision_id") or ""),
            )
        )
        with self._lock:
            for event in rows:
                append_seq = event_append_seq(event)
                if append_seq <= self._append_cursor:
                    continue
                if self._belongs(event):
                    self._track_event(event)
                self._append_cursor = append_seq
            if direct_tail is not None:
                self._append_cursor = max(self._append_cursor, direct_tail)
            self._loaded = True

    def ensure_loaded(self) -> None:
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
            "expected_cost": validate_reservation_cost(expected_cost),
        }
        with self._lock:
            self._track_assignment(decision_id=str(decision_id), payload=payload)
        self.refresh()

    def _purge_expired(self, *, cutoff_ms: int) -> None:
        max_dirty = False
        while self._candidate_window and self._candidate_window[0][0] < cutoff_ms:
            _assigned_at, decision_id, subject_hash, _expected_cost = (
                self._candidate_window.popleft()
            )
            self._candidate_assignments.pop(decision_id, None)
            self._candidate_actual_costs.pop(decision_id, None)
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

    def _cost_exposure(self) -> tuple[float, float, float]:
        expected = sum(row[2] for row in self._candidate_assignments.values())
        actual = sum(
            cost
            for decision_id, cost in self._candidate_actual_costs.items()
            if decision_id in self._candidate_assignments
        )
        pending = sum(
            row[2]
            for decision_id, row in self._candidate_assignments.items()
            if decision_id not in self._candidate_actual_costs
        )
        return expected, actual, actual + pending

    def metrics(self, *, candidate_pct: float) -> dict[str, float | int]:
        self.refresh()
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._purge_expired(cutoff_ms=now_ms - 24 * 60 * 60 * 1000)
            counts = self._stage_counts.get(float(candidate_pct), Counter())
            control = int(counts.get(ExperimentArm.CONTROL.value, 0))
            candidate = int(counts.get(ExperimentArm.CANDIDATE.value, 0))
            first = self._stage_first_assignment_ms.get(float(candidate_pct), 0)
            expected_cost, actual_cost, exposure = self._cost_exposure()
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
                "candidate_expected_cost_24h": expected_cost,
                "candidate_actual_cost_24h": actual_cost,
                "candidate_cost_24h": exposure,
                "candidate_max_actions_per_subject_24h": self._candidate_max_subject_count,
                "duration_seconds": (
                    max(0.0, (now_ms - first) / 1000.0) if first else 0.0
                ),
                "assignment_count": control + candidate,
                "mature_assignment_count": 0,
                "outcome_count": 0,
                "mature_outcome_count": 0,
            }


__all__ = ["LiveCanaryAssignmentSafety"]
