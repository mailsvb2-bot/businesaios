from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DecisionObservation:
    source: str
    status: str
    governance_called: bool
    executor_called: bool
    events: tuple[str, ...]
    metrics: tuple[str, ...]
    traces: tuple[str, ...]
    payload: dict[str, Any]


def validate_observation_invariants(obs: DecisionObservation) -> list[str]:
    errors: list[str] = []

    if obs.source != "DecisionCore":
        errors.append("decision source must remain DecisionCore")

    if obs.status == "executed" and not obs.governance_called:
        errors.append("executed path bypassed governance")

    if obs.status == "executed" and not obs.executor_called:
        errors.append("executed path did not reach executor")

    if obs.status == "blocked" and obs.executor_called:
        errors.append("blocked path executed side effects")

    if obs.status not in {"executed", "blocked"}:
        errors.append(f"unexpected status: {obs.status}")

    required_events = {"decision.evaluated", f"decision.{obs.status}"}
    if not required_events.issubset(set(obs.events)):
        errors.append("observability events are incomplete")

    if not {"decision.latency_ms", "decision.count"}.issubset(set(obs.metrics)):
        errors.append("decision metrics are incomplete")

    if "decision.trace" not in set(obs.traces):
        errors.append("decision trace is missing")

    if obs.status == "blocked" and obs.payload.get("reason") != "governance_rejected":
        errors.append("blocked path must fail closed with governance_rejected")

    return errors
