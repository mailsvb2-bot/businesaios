from __future__ import annotations

import math
import time
from collections import Counter
from collections.abc import Iterable
from typing import Any

from core.experiments.assignment import ExperimentArm, ExperimentAssignment
from core.experiments.live_canary_events import (
    BUSINESS_OUTCOME_OBSERVED,
    CANDIDATE_ACTION_EXECUTED,
    CONTROL_ACTION_EXECUTED,
    EXPERIMENT_ASSIGNMENT,
    EXPERIMENT_CREATED,
)


def _data(event: Any) -> dict[str, Any]:
    return event if isinstance(event, dict) else vars(event)


def _payload(event: Any) -> dict[str, Any]:
    return dict(_data(event).get("payload") or {})


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _same_stage(value: object, candidate_pct: float | None) -> bool:
    if candidate_pct is None:
        return True
    return abs(_finite(value, -1.0) - float(candidate_pct)) < 1e-9


def _assert_idempotent(existing: dict[str, Any], expected: dict[str, Any]) -> None:
    conflicts = [
        key
        for key, value in expected.items()
        if key in existing and existing.get(key) != value
    ]
    if conflicts:
        raise RuntimeError(
            "LIVE_CANARY_IDEMPOTENCY_CONFLICT:" + ",".join(sorted(conflicts))
        )


class LiveCanaryLedger:
    """Tenant-scoped evidence ledger for randomized live traffic."""

    def __init__(
        self,
        event_log: Any,
        *,
        experiment_id: str,
        candidate_policy_id: str,
        outcome_window_seconds: int = 0,
    ) -> None:
        self.event_log = event_log
        self.experiment_id = str(experiment_id)
        self.candidate_policy_id = str(candidate_policy_id)
        self.outcome_window_seconds = max(0, int(outcome_window_seconds))

    def _events(self) -> Iterable[Any]:
        iterator = getattr(self.event_log, "iter_events", None)
        if not callable(iterator):
            raise RuntimeError("LIVE_CANARY_EVENT_LEDGER_UNAVAILABLE")
        return iterator()

    def events_for_decision(self, decision_id: str, event_type: str) -> list[Any]:
        get_events = getattr(self.event_log, "get_events", None)
        if callable(get_events):
            return list(get_events(str(decision_id), str(event_type)))
        return [
            event
            for event in self._events()
            if str(_data(event).get("decision_id") or "") == str(decision_id)
            and str(_data(event).get("event_type") or "") == str(event_type)
        ]

    def _belongs(self, event: Any) -> bool:
        payload = _payload(event)
        return (
            payload.get("experiment_id") == self.experiment_id
            and payload.get("candidate_policy_id") == self.candidate_policy_id
        )

    def assignment_for_decision(self, decision_id: str) -> dict[str, Any] | None:
        matching = [
            event
            for event in self.events_for_decision(decision_id, EXPERIMENT_ASSIGNMENT)
            if self._belongs(event)
        ]
        return _payload(matching[-1]) if matching else None

    def _emit(
        self,
        *,
        event_type: str,
        decision_id: str,
        correlation_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        row = {
            "experiment_id": self.experiment_id,
            "candidate_policy_id": self.candidate_policy_id,
            **payload,
        }
        return self.event_log.emit(
            event_type=event_type,
            source="live_canary",
            user_id="experiment",
            decision_id=str(decision_id),
            correlation_id=correlation_id,
            payload=row,
        )

    def record_experiment_created(
        self,
        *,
        decision_id: str,
        correlation_id: str | None,
        candidate_pct: float,
        allowed_actions: tuple[str, ...],
    ) -> dict[str, Any]:
        expected = {
            "candidate_pct": float(candidate_pct),
            "allowed_actions": list(allowed_actions),
        }
        existing = [
            event
            for event in self.events_for_decision(decision_id, EXPERIMENT_CREATED)
            if self._belongs(event)
        ]
        if existing:
            row = _payload(existing[-1])
            _assert_idempotent(row, expected)
            return row
        return self._emit(
            event_type=EXPERIMENT_CREATED,
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload={**expected, "created_at_ms": int(time.time() * 1000)},
        )

    def record_assignment(
        self,
        assignment: ExperimentAssignment,
        *,
        decision_id: str,
        correlation_id: str | None,
        production_policy_id: str,
        action: str,
        candidate_pct: float,
        expected_cost: float = 0.0,
        assigned_at_ms: int | None = None,
    ) -> dict[str, Any]:
        expected = {
            "tenant_id": assignment.tenant_id,
            "purpose": assignment.purpose,
            "subject_hash": assignment.subject_hash,
            "arm": assignment.arm.value,
            "bucket": assignment.bucket,
            "production_policy_id": str(production_policy_id),
            "action": str(action),
            "candidate_pct": float(candidate_pct),
            "expected_cost": _finite(expected_cost),
            "eligible": assignment.eligible,
            "reason": assignment.reason,
        }
        existing = self.assignment_for_decision(decision_id)
        if existing is not None:
            _assert_idempotent(existing, expected)
            return existing
        return self._emit(
            event_type=EXPERIMENT_ASSIGNMENT,
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload={
                **expected,
                "assigned_at_ms": int(assigned_at_ms or time.time() * 1000),
            },
        )

    def record_execution(
        self,
        *,
        decision_id: str,
        correlation_id: str | None,
        arm: ExperimentArm | str,
        action: str,
        ok: bool,
        cost: float,
        proof_event_type: str,
        evidence_ref: str,
        critical_violation: bool = False,
        complaint: bool = False,
        executed_at_ms: int | None = None,
    ) -> dict[str, Any]:
        normalized_arm = ExperimentArm(str(getattr(arm, "value", arm)))
        event_type = (
            CANDIDATE_ACTION_EXECUTED
            if normalized_arm is ExperimentArm.CANDIDATE
            else CONTROL_ACTION_EXECUTED
        )
        expected = {
            "arm": normalized_arm.value,
            "action": str(action),
            "ok": bool(ok),
            "cost": _finite(cost),
            "proof_event_type": str(proof_event_type),
            "evidence_ref": str(evidence_ref),
            "critical_violation": bool(critical_violation),
            "complaint": bool(complaint),
        }
        existing = [
            event
            for event in self.events_for_decision(decision_id, event_type)
            if self._belongs(event)
        ]
        if existing:
            row = _payload(existing[-1])
            _assert_idempotent(row, expected)
            return row
        if not expected["proof_event_type"] or not expected["evidence_ref"]:
            raise ValueError("proof_event_type and evidence_ref are required")
        return self._emit(
            event_type=event_type,
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload={
                **expected,
                "executed_at_ms": int(executed_at_ms or time.time() * 1000),
            },
        )

    def record_outcome(
        self,
        *,
        decision_id: str,
        correlation_id: str | None,
        arm: ExperimentArm | str,
        outcome_type: str,
        success: bool,
        value: float = 0.0,
        revenue: float = 0.0,
        evidence_ref: str,
        observed_at_ms: int | None = None,
    ) -> dict[str, Any]:
        normalized_arm = ExperimentArm(str(getattr(arm, "value", arm)))
        if normalized_arm is ExperimentArm.INELIGIBLE:
            raise ValueError("ineligible assignments cannot receive outcomes")
        expected = {
            "arm": normalized_arm.value,
            "outcome_type": str(outcome_type),
            "success": bool(success),
            "value": _finite(value),
            "revenue": _finite(revenue),
            "evidence_ref": str(evidence_ref),
            "counterfactual": False,
        }
        if not expected["outcome_type"] or not expected["evidence_ref"]:
            raise ValueError("outcome_type and evidence_ref are required")
        existing = [
            event
            for event in self.events_for_decision(
                decision_id,
                BUSINESS_OUTCOME_OBSERVED,
            )
            if self._belongs(event)
            and _payload(event).get("outcome_type") == expected["outcome_type"]
        ]
        if existing:
            row = _payload(existing[-1])
            _assert_idempotent(row, expected)
            return row
        return self._emit(
            event_type=BUSINESS_OUTCOME_OBSERVED,
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload={
                **expected,
                "observed_at_ms": int(observed_at_ms or time.time() * 1000),
            },
        )

    def metrics(self, *, candidate_pct: float | None = None) -> dict[str, float | int]:
        rows = [
            (_data(event), _payload(event))
            for event in self._events()
            if self._belongs(event)
        ]
        now_ms = int(time.time() * 1000)
        maturity_cutoff_ms = now_ms - self.outcome_window_seconds * 1000
        rolling_cutoff_ms = now_ms - 24 * 60 * 60 * 1000

        assignments: dict[str, dict[str, Any]] = {}
        for data, payload in rows:
            if str(data.get("event_type") or "") != EXPERIMENT_ASSIGNMENT:
                continue
            if payload.get("eligible") is not True:
                continue
            if not _same_stage(payload.get("candidate_pct"), candidate_pct):
                continue
            decision_id = str(data.get("decision_id") or "")
            existing = assignments.get(decision_id)
            if existing is not None and existing != payload:
                raise RuntimeError("LIVE_CANARY_DUPLICATE_ASSIGNMENT_CONFLICT")
            assignments[decision_id] = payload

        metrics: dict[str, float | int] = {
            "control_assignments": 0,
            "candidate_assignments": 0,
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
            "mature_control_outcomes": 0,
            "mature_candidate_outcomes": 0,
            "mature_control_successes": 0,
            "mature_candidate_successes": 0,
            "control_revenue": 0.0,
            "candidate_revenue": 0.0,
            "mature_control_revenue": 0.0,
            "mature_candidate_revenue": 0.0,
            "critical_violations": 0,
            "first_assignment_ms": 0,
            "last_event_ms": 0,
            "candidate_actions_24h": 0,
            "candidate_cost_24h": 0.0,
            "candidate_max_actions_per_subject_24h": 0,
        }
        mature_decisions: set[str] = set()
        for decision_id, assignment in assignments.items():
            arm = str(assignment.get("arm") or "")
            prefix = "candidate" if arm == ExperimentArm.CANDIDATE.value else "control"
            assigned_at = int(assignment.get("assigned_at_ms") or 0)
            metrics[f"{prefix}_assignments"] = int(
                metrics[f"{prefix}_assignments"]
            ) + 1
            if assigned_at and assigned_at <= maturity_cutoff_ms:
                mature_decisions.add(decision_id)
                metrics[f"mature_{prefix}_assignments"] = int(
                    metrics[f"mature_{prefix}_assignments"]
                ) + 1
            first = int(metrics["first_assignment_ms"])
            if assigned_at and (not first or assigned_at < first):
                metrics["first_assignment_ms"] = assigned_at

        execution_keys: set[tuple[str, str]] = set()
        outcome_keys: set[tuple[str, str]] = set()
        subject_actions: Counter[str] = Counter()
        for data, payload in rows:
            decision_id = str(data.get("decision_id") or "")
            assignment = assignments.get(decision_id)
            if assignment is None:
                continue
            kind = str(data.get("event_type") or "")
            arm = str(assignment.get("arm") or "")
            prefix = "candidate" if arm == ExperimentArm.CANDIDATE.value else "control"
            timestamp = int(
                payload.get("executed_at_ms")
                or payload.get("observed_at_ms")
                or 0
            )
            if timestamp:
                metrics["last_event_ms"] = max(
                    int(metrics["last_event_ms"]),
                    timestamp,
                )

            if kind in {CONTROL_ACTION_EXECUTED, CANDIDATE_ACTION_EXECUTED}:
                key = (decision_id, kind)
                if key in execution_keys:
                    continue
                execution_keys.add(key)
                if str(payload.get("arm") or "") != arm:
                    raise RuntimeError("LIVE_CANARY_EXECUTION_ARM_CONFLICT")
                cost = _finite(payload.get("cost"))
                metrics[f"{prefix}_executions"] = int(
                    metrics[f"{prefix}_executions"]
                ) + 1
                metrics[f"{prefix}_cost"] = float(
                    metrics[f"{prefix}_cost"]
                ) + cost
                if payload.get("ok") is not True:
                    metrics[f"{prefix}_errors"] = int(
                        metrics[f"{prefix}_errors"]
                    ) + 1
                if bool(payload.get("complaint")):
                    metrics[f"{prefix}_complaints"] = int(
                        metrics[f"{prefix}_complaints"]
                    ) + 1
                if bool(payload.get("critical_violation")):
                    metrics["critical_violations"] = int(
                        metrics["critical_violations"]
                    ) + 1
                if prefix == "candidate" and timestamp >= rolling_cutoff_ms:
                    metrics["candidate_actions_24h"] = int(
                        metrics["candidate_actions_24h"]
                    ) + 1
                    metrics["candidate_cost_24h"] = float(
                        metrics["candidate_cost_24h"]
                    ) + cost
                    subject_actions[str(assignment.get("subject_hash") or "")] += 1
            elif kind == BUSINESS_OUTCOME_OBSERVED:
                outcome_type = str(payload.get("outcome_type") or "")
                key = (decision_id, outcome_type)
                if key in outcome_keys:
                    continue
                outcome_keys.add(key)
                if str(payload.get("arm") or "") != arm:
                    raise RuntimeError("LIVE_CANARY_OUTCOME_ARM_CONFLICT")
                revenue = _finite(payload.get("revenue"))
                metrics[f"{prefix}_outcomes"] = int(
                    metrics[f"{prefix}_outcomes"]
                ) + 1
                if bool(payload.get("success")):
                    metrics[f"{prefix}_successes"] = int(
                        metrics[f"{prefix}_successes"]
                    ) + 1
                metrics[f"{prefix}_revenue"] = float(
                    metrics[f"{prefix}_revenue"]
                ) + revenue
                if decision_id in mature_decisions:
                    metrics[f"mature_{prefix}_outcomes"] = int(
                        metrics[f"mature_{prefix}_outcomes"]
                    ) + 1
                    if bool(payload.get("success")):
                        metrics[f"mature_{prefix}_successes"] = int(
                            metrics[f"mature_{prefix}_successes"]
                        ) + 1
                    metrics[f"mature_{prefix}_revenue"] = float(
                        metrics[f"mature_{prefix}_revenue"]
                    ) + revenue

        metrics["candidate_max_actions_per_subject_24h"] = max(
            subject_actions.values(),
            default=0,
        )
        first = int(metrics["first_assignment_ms"])
        metrics["duration_seconds"] = (
            max(0.0, (now_ms - first) / 1000.0) if first else 0.0
        )
        metrics["assignment_count"] = int(
            metrics["control_assignments"]
        ) + int(metrics["candidate_assignments"])
        metrics["mature_assignment_count"] = int(
            metrics["mature_control_assignments"]
        ) + int(metrics["mature_candidate_assignments"])
        metrics["outcome_count"] = int(metrics["control_outcomes"]) + int(
            metrics["candidate_outcomes"]
        )
        metrics["mature_outcome_count"] = int(
            metrics["mature_control_outcomes"]
        ) + int(metrics["mature_candidate_outcomes"])
        return metrics


__all__ = ["LiveCanaryLedger"]
