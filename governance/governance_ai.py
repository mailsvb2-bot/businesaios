"""GovernanceAI (canonical).

Governance does not make business decisions.
It only evaluates metrics and provides recommendations to DecisionCore.
"""

from __future__ import annotations


class GovernanceAI:
    def evaluate(self, metrics: dict) -> dict:
        return {
            "risk_score": metrics.get("anomaly_score", 0.0),
            "recommendation": "observe",
        }


__all__ = ["GovernanceAI"]