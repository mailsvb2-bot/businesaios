from __future__ import annotations


class RefundQualityTracker:
    def penalty(self, outcome: dict[str, object]) -> float:
        return 0.4 if outcome.get("returned") else 0.0
