from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

CANON_BUSINESS_OUTCOME_CONTRACT = True


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _finite(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _ratio(value: object) -> float:
    return max(0.0, min(1.0, _finite(value) or 0.0))


@dataclass(frozen=True)
class BusinessOutcomeV1:
    outcome_id: str
    tenant_id: str
    business_id: str
    run_id: str
    intent_id: str
    decision_id: str
    action_id: str
    action_type: str
    goal: str
    status: str
    attempted: bool
    executed: bool
    verified: bool
    goal_achieved: bool
    goal_terminal: bool
    completion_ratio: float
    success_confidence: float
    revenue_amount: float | None = None
    revenue_verified: bool = False
    evidence_status: str = "unknown"
    source_of_truth: str = "feedback_contract"
    external_refs: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    @classmethod
    def from_feedback(
        cls, *, tenant_id: str, business_id: str, run_id: str, intent_id: str,
        decision_id: str, action_id: str, action_type: str, goal: str, status: str,
        feedback: Mapping[str, Any],
    ) -> BusinessOutcomeV1:
        data = dict(feedback or {})
        goal_eval = _dict(data.get("goal_evaluation"))
        revenue = _dict(data.get("revenue_outcome"))
        outcome = cls(
            f"outcome:{action_id}", tenant_id.strip(), business_id.strip(), run_id.strip(),
            intent_id.strip(), decision_id.strip(), action_id.strip(), action_type.strip(),
            str(goal or ""), str(status or "unknown").strip() or "unknown",
            bool(data.get("attempted")), bool(data.get("executed")), bool(data.get("verified")),
            bool(goal_eval.get("achieved", data.get("goal_reached"))), bool(goal_eval.get("terminal")),
            _ratio(goal_eval.get("completion_ratio", data.get("goal_score"))),
            _ratio(goal_eval.get("success_confidence")), _finite(revenue.get("revenue_amount")),
            bool(revenue.get("verified")), str(data.get("evidence_status") or data.get("verification_status") or "unknown"),
            str(_dict(data.get("execution_feedback")).get("source_of_truth") or "feedback_contract"),
            tuple(str(value) for value in data.get("external_refs") or () if str(value).strip()),
            _dict(data.get("normalized_outcome")),
        )
        required = (
            outcome.outcome_id, outcome.tenant_id, outcome.business_id, outcome.run_id,
            outcome.intent_id, outcome.decision_id, outcome.action_id, outcome.action_type, outcome.status,
        )
        if not all(value and value.strip() == value for value in required):
            raise ValueError("invalid business outcome identity")
        return outcome

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.__dict__,
            "external_refs": list(self.external_refs),
            "metrics": dict(self.metrics),
        }


__all__ = ["CANON_BUSINESS_OUTCOME_CONTRACT", "BusinessOutcomeV1"]
