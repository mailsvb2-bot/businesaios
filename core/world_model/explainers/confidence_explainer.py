from __future__ import annotations

from core.world_model.types import ConfidenceReport, FreshnessReport


class ConfidenceExplainer:
    def explain(self, *, confidence: ConfidenceReport, freshness: FreshnessReport) -> dict:
        return {
            "confidence_score": confidence.score,
            "confidence_reasons": list(confidence.reasons),
            "freshness_age_ms": dict(freshness.age_ms),
        }
