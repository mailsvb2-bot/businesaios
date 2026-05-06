from __future__ import annotations

"""Canonical optimization gates surface with compat alias submodules."""

class ApprovalGate:
    def allows(self, payload: dict) -> bool:
        return bool(payload.get("approved", False))

class ConfidenceGate:
    def allows(self, payload: dict) -> bool:
        return float(payload.get("confidence", 0.0)) >= float(payload.get("min_confidence", 0.0))

class CostGate:
    def allows(self, payload: dict) -> bool:
        return float(payload.get("cost", 0.0)) <= float(payload.get("max_cost", float("inf")))

class PromotionGate:
    def allows(self, payload: dict) -> bool:
        return bool(payload.get("evaluation_passed", False) and payload.get("safety_passed", False))

class ReleaseReadinessGate:
    def allows(self, payload: dict) -> bool:
        required = (
            payload.get("evaluation_passed", False),
            payload.get("safety_passed", False),
            payload.get("approved", False),
            payload.get("reproducible", False),
        )
        return all(required)

class ReproducibilityGate:
    def allows(self, payload: dict) -> bool:
        return bool(payload.get("reproducible", False))

class RollbackGate:
    def allows(self, payload: dict) -> bool:
        return bool(payload.get("degraded", False) or payload.get("unsafe", False))

class SafetyGate:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("unsafe", False))

_ALIAS_EXPORTS = {
    "approval_gate": "ApprovalGate",
    "confidence_gate": "ConfidenceGate",
    "cost_gate": "CostGate",
    "promotion_gate": "PromotionGate",
    "release_readiness_gate": "ReleaseReadinessGate",
    "reproducibility_gate": "ReproducibilityGate",
    "rollback_gate": "RollbackGate",
    "safety_gate": "SafetyGate",
}

__all__ = [
    "ApprovalGate",
    "ConfidenceGate",
    "CostGate",
    "PromotionGate",
    "ReleaseReadinessGate",
    "ReproducibilityGate",
    "RollbackGate",
    "SafetyGate",
] + list(_ALIAS_EXPORTS)
