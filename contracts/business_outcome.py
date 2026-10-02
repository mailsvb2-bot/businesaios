from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

CANON_BUSINESS_OUTCOME_CONTRACT = True
BUSINESS_OUTCOME_TAXONOMY = (
    "technical",
    "operational",
    "customer",
    "financial",
    "strategic",
)


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
    evidence_refs: tuple[str, ...] = ()
    derived_fact_ref: str = ""

    @classmethod
    def from_feedback(
        cls, *, tenant_id: str, business_id: str, run_id: str, intent_id: str,
        decision_id: str, action_id: str, action_type: str, goal: str, status: str,
        feedback: Mapping[str, Any], evidence_refs: tuple[str, ...] = (),
        derived_fact_ref: str = "",
    ) -> BusinessOutcomeV1:
        data = dict(feedback or {})
        goal_eval = _dict(data.get("goal_evaluation"))
        revenue = _dict(data.get("revenue_outcome"))
        metrics = _dict(data.get("normalized_outcome"))
        for key in ("interaction_id", "customer_id", "conversion_id"):
            value = str(data.get(key) or "").strip()
            if value and not str(metrics.get(key) or "").strip():
                metrics[key] = value
        for key in ("payment_id", "invoice_id", "order_id"):
            value = str(revenue.get(key) or "").strip()
            if value and not str(metrics.get(key) or "").strip():
                metrics[key] = value
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
            metrics,
            evidence_refs=tuple(dict.fromkeys(str(value).strip() for value in evidence_refs if str(value).strip())),
            derived_fact_ref=str(derived_fact_ref or "").strip(),
        )
        required = (
            outcome.outcome_id, outcome.tenant_id, outcome.business_id, outcome.run_id,
            outcome.intent_id, outcome.decision_id, outcome.action_id, outcome.action_type, outcome.status,
        )
        if not all(value and value.strip() == value for value in required):
            raise ValueError("invalid business outcome identity")
        return outcome

    def taxonomy(self) -> tuple[str, ...]:
        """Return deterministic Phase 13 outcome categories without rewriting V1 storage."""
        metrics = _dict(self.metrics)
        categories: list[str] = []
        if self.attempted or self.executed or self.verified:
            categories.append("technical")
        if self.executed or self.verified:
            categories.append("operational")
        if any(str(metrics.get(key) or "").strip() for key in ("customer_id", "conversion_id", "customer_impact")):
            categories.append("customer")
        if self.revenue_verified or self.revenue_amount not in (None, 0.0) or any(str(metrics.get(key) or "").strip() for key in ("payment_id", "invoice_id", "order_id")):
            categories.append("financial")
        if self.goal_achieved or self.goal_terminal:
            categories.append("strategic")
        return tuple(categories)

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.__dict__,
            "external_refs": list(self.external_refs),
            "evidence_refs": list(self.evidence_refs),
            "metrics": dict(self.metrics),
        }


__all__ = ["BUSINESS_OUTCOME_TAXONOMY", "CANON_BUSINESS_OUTCOME_CONTRACT", "BusinessOutcomeV1"]
