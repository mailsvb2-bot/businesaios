from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_CAC_LEARNING_ENGINE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True, slots=True)
class CACLearningSnapshot:
    estimated_cac: float
    acquired_customers: int
    payback_hint_months: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_cac": float(self.estimated_cac),
            "acquired_customers": int(self.acquired_customers),
            "payback_hint_months": float(self.payback_hint_months),
            "metadata": dict(self.metadata),
        }


class CACLearningEngine:
    def estimate(self, *, budget_guard_result: Mapping[str, Any] | None, revenue_verification_result: Mapping[str, Any] | None) -> CACLearningSnapshot:
        budget_payload = _safe_dict(budget_guard_result)
        revenue_payload = _safe_dict(revenue_verification_result)
        spend_limits = _safe_dict(budget_payload.get("spend_limits"))
        requested_budget = _safe_float(spend_limits.get("approved_budget") or spend_limits.get("requested_budget"))
        projected = _safe_dict(revenue_payload.get("projected_outcome"))
        acquired_customers = max(0, _safe_int(projected.get("acquired_customers") or projected.get("customer_count") or projected.get("bookings_count")))
        realized_revenue = _safe_float(revenue_payload.get("revenue_amount"))
        estimated_cac = requested_budget / acquired_customers if acquired_customers > 0 else requested_budget
        payback_hint_months = requested_budget / max(realized_revenue, 1e-6) if realized_revenue > 0.0 and requested_budget > 0.0 else 0.0
        return CACLearningSnapshot(
            estimated_cac=estimated_cac,
            acquired_customers=acquired_customers,
            payback_hint_months=payback_hint_months,
            metadata={"owner": "execution.cac_learning_engine"},
        )


__all__ = ["CANON_CAC_LEARNING_ENGINE", "CACLearningEngine", "CACLearningSnapshot"]
