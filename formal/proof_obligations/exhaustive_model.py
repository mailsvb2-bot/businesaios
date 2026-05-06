from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from typing import Any

from .invariants import DecisionObservation, validate_observation_invariants


@dataclass(frozen=True)
class RuntimeDecisionModelCase:
    governance_allowed: bool
    has_action: bool
    emit_events: bool
    emit_metrics: bool
    emit_trace: bool


def _simulate_case(case: RuntimeDecisionModelCase) -> DecisionObservation:
    status = "executed" if case.governance_allowed and case.has_action else "blocked"
    governance_called = True
    executor_called = status == "executed"
    events = ["decision.evaluated"]
    if case.emit_events:
        events.append(f"decision.{status}")
    metrics = ["decision.latency_ms"]
    if case.emit_metrics:
        metrics.append("decision.count")
    traces = ["decision.trace"] if case.emit_trace else []
    payload: dict[str, Any] = {"action_present": case.has_action, "status": status}
    if status == "blocked":
        payload["reason"] = "governance_rejected"
    return DecisionObservation(
        source="DecisionCore",
        status=status,
        governance_called=governance_called,
        executor_called=executor_called,
        events=tuple(events),
        metrics=tuple(metrics),
        traces=tuple(traces),
        payload=payload,
    )


def verify_runtime_decision_model() -> dict[str, Any]:
    checked = 0
    failures: list[dict[str, Any]] = []
    for values in product([False, True], repeat=5):
        case = RuntimeDecisionModelCase(*values)
        obs = _simulate_case(case)
        errors = validate_observation_invariants(obs)
        checked += 1
        if errors:
            failures.append({"case": asdict(case), "errors": errors})
    passing_cases = checked - len(failures)
    return {
        "checked_cases": checked,
        "passing_cases": passing_cases,
        "failing_cases": failures,
        "ok": not failures,
    }
