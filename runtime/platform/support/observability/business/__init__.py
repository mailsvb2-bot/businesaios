from __future__ import annotations

"""Canonical business observability surface with compat alias submodules."""

class CostMetrics:
    def summarize(self, cost: float) -> dict[str, float]:
        return {"cost": cost}

class DriftMetrics:
    def summarize(self, drift: float) -> dict[str, float]:
        return {"drift": drift}

class KPIMetrics:
    def summarize(self, value: float) -> dict[str, float]:
        return {"kpi": value}

class PromotionMetrics:
    def summarize(self, approved: bool) -> dict[str, int]:
        return {"promoted": int(approved)}

class RollbackMetrics:
    def summarize(self, rollback: bool) -> dict[str, int]:
        return {"rollback": int(rollback)}

_ALIAS_EXPORTS = {
    "cost_metrics": "CostMetrics",
    "drift_metrics": "DriftMetrics",
    "kpi_metrics": "KPIMetrics",
    "promotion_metrics": "PromotionMetrics",
    "rollback_metrics": "RollbackMetrics",
}

__all__ = [
    "CostMetrics",
    "DriftMetrics",
    "KPIMetrics",
    "PromotionMetrics",
    "RollbackMetrics",
] + list(_ALIAS_EXPORTS)
