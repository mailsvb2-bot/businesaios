from __future__ import annotations

class RouteQualityEngine:
    def evaluate(self, *, routed_revenue: float, quality_score: float) -> float:
        return max(0.0, min(1.0, 0.5 * min(1.0, routed_revenue / 500.0) + 0.5 * quality_score))
