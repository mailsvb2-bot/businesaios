from __future__ import annotations


class QualityRecoveryPlanner:
    def plan(self, quality_score: float) -> tuple[str, ...]:
        if quality_score < 0.4:
            return ("manual_review", "pause_routing")
        if quality_score < 0.6:
            return ("coach_response_quality",)
        return ()
